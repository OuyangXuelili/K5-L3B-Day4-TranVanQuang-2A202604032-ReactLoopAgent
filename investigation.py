"""Track evidence requested by the user, independently of the model's draft answer."""
import json
import re
import sys
import unicodedata
from urllib.parse import urlsplit

from status_tools import HOSTS


def normalize(text):
    text = text.casefold().replace('đ', 'd')
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


class Investigation:
    """Requirements come only from the question and official incident references.

    This is an evidence checklist, not an answer generator. The model must still
    issue all tool calls, and failed lookups permit an honest partial answer.
    """
    def __init__(self, question, schemas, tools):
        self.status_tools = {}
        for item in schemas:
            function = item['function']
            name = function['name']
            if name == 'get_status':
                providers = function['parameters']['properties']['provider'].get('enum', [])
                self.status_tools.update({p: name for p in providers})
            elif name.startswith('get_') and name.endswith('_status'):
                self.status_tools[name[4:-7]] = name
        self.has_details = any(s['function']['name'] == 'get_incident_details' for s in schemas)
        self.status_attempted, self.details_attempted = set(), set()
        self.status_unavailable, self.status_succeeded = {}, set()
        self.required_status, self.required_details = set(), set()
        self.detail_reasons = {}
        self.hosts = {urlsplit(url).hostname: p for p, url in HOSTS.items()}
        for cls in type(tools).__mro__:
            configured = getattr(sys.modules.get(cls.__module__), 'HOSTS', {})
            if isinstance(configured, dict):
                self.hosts.update({urlsplit(url).hostname: p for p, url in configured.items()})

        q = normalize(question)
        self.question_words = {w.rstrip('s') for w in re.findall(r'[a-z]{3,}', q)} - {
            'incident', 'statu', 'with', 'and', 'the', 'issue', *self.status_tools}
        self.topic_hints = {}
        stop = {'va', 'co', 'la', 'tai', 'trong', 'voi', 'nhung', 'dang', 'hien',
                'incident', 'status', 'trang', 'thai', 'and', 'is', 'are', 'currently'}
        for provider in self.status_tools:
            match = re.search(r'\b' + re.escape(provider) + r'\b', question, re.I)
            if not match:
                continue
            words = []
            tail = question[match.end():]
            if tail and tail[0] in ',.:;':
                continue
            for token in tail.split()[:4]:
                if not re.fullmatch('[A-Za-z]+', token) or normalize(token) in stop:
                    break
                words.append(token)
            if words:
                self.topic_hints[provider] = ' '.join(words)
        self.disabled = any(s in q for s in ('dung kiem tra', 'khong kiem tra', 'khong goi tool',
                                              'khong dung tool', 'do not use tools', "don't use tools"))
        self.follow_links = any(s in q for s in ('theo lien ket', 'tro sang incident', 'follow the link')) or (
            'doc ' in q and any(s in q for s in ('incident lien quan', 'incident khac')))
        summary = ('tong hop status' in q or 'tong hop trang thai' in q) and not any(
            s in q for s in ('incident', 'timeline', 'doi chieu', 'pham vi'))
        self.needs_details = not summary and any(s in q for s in (
            'incident', 'su co', 'pham vi', 'anh huong', 'nguyen nhan', 'doi chieu',
            'timeline', 'thanh phan', 'component', 'impact', 'root cause'))
        positions = [(match.start(), p) for p in self.status_tools
                     for match in re.finditer(r'\b' + re.escape(normalize(p)) + r'\b', q)]
        self.question_providers = {p for _, p in positions}
        self.latest_requested = any(s in q for s in ('moi nhat', 'gan nhat', 'latest', 'most recent'))

        # IDs are taken verbatim from the user's question, never from eval answers.
        for match in re.finditer(r'(?<![a-z0-9-])[a-z0-9][a-z0-9-]{7,63}(?![a-z0-9-])', question, re.I):
            token = match.group()
            prefix = normalize(question[max(0, match.start() - 80):match.start()])
            alphanumeric_id = bool(re.search('[a-z]', token, re.I) and re.search('[0-9]', token))
            named_id = bool(re.search(r'(?:incident|ma|id)\s*[:#]?\s*$', prefix)) and '-' in token
            if not ((alphanumeric_id and any(s in q for s in ('incident', 'su co'))) or named_id) or not positions:
                continue
            preceding = [(position, provider) for position, provider in positions if position < match.start()]
            target = (max(preceding)[1] if preceding else
                      min(positions, key=lambda item: abs(item[0] - match.start()))[1])
            self._require_details(target, token, 'ID incident được hỏi trực tiếp')

        asks_status = not self.required_details or any(s in q for s in (
            'status', 'hien ', 'hien tai', 'dang outage', 'dang hoat dong', 'dang the nao',
            'current status', 'currently down'))
        if asks_status:
            self.required_status = {p for _, p in positions}
        if self.disabled:
            self.required_status.clear()
            self.required_details.clear()

    def _require_details(self, provider, incident_id, reason):
        if self.has_details and provider in self.status_tools:
            self.required_details.add((provider, incident_id))
            self.detail_reasons[(provider, incident_id)] = reason

    def observe(self, name, args, result, *, retry_allowed=False):
        if self.disabled or not isinstance(args, dict):
            return
        target = args.get('provider') if name == 'get_status' else next(
            (p for p, tool_name in self.status_tools.items() if tool_name == name), None)
        valid_attempt = result.get('error') != 'INVALID_ARGUMENTS' and not retry_allowed
        if target in self.status_tools and name == self.status_tools[target]:
            if retry_allowed:
                self.required_status.add(target)
                self.status_attempted.discard(target)
            if valid_attempt:
                self.status_attempted.add(target)
            if result.get('ok') is False or result.get('error'):
                if target not in self.status_succeeded:
                    self.status_unavailable[target] = str(result.get('error', 'TOOL_ERROR'))[:80]
            else:
                self.status_succeeded.add(target)
                self.status_unavailable.pop(target, None)
            source = result.get('source')
            if isinstance(source, str):
                try:
                    self.hosts.setdefault(urlsplit(source).hostname, target)
                except ValueError:
                    pass
            in_scope = not self.question_providers or target in self.question_providers
            if self.needs_details and in_scope and not any(p == target for p, _ in self.required_details):
                incidents = result.get('incidents', [])
                if incidents:
                    # Prefer a title matching the question over an unrelated first item
                    # when a model used an unfiltered provider summary.
                    def relevance(incident):
                        words = {w.rstrip('s') for w in re.findall(r'[a-z]{3,}', normalize(incident.get('name', '')))}
                        return sum(len(w) for w in self.question_words.intersection(words))
                    if self.latest_requested:
                        # Status APIs return recent incidents in provider order.
                        # Extra matching words must not outweigh recency, and
                        # updated_at must not be mistaken for incident start time.
                        selected = next((item for item in incidents if relevance(item) > 0), incidents[0])
                    else:
                        selected = max(incidents, key=relevance)
                else:
                    selected = {}
                if isinstance(selected.get('id'), str):
                    self._require_details(target, selected['id'],
                                          'Đọc incident tìm được để xác minh phạm vi/timeline')
        if name != 'get_incident_details':
            return
        target, incident_id = args.get('provider'), args.get('incident_id')
        if isinstance(target, str) and isinstance(incident_id, str) and valid_attempt:
            self.details_attempted.add((target, incident_id))
        if not self.follow_links or result.get('ok') is not True:
            return
        for update in result.get('updates', []):
            for url in re.findall(r'https?://[^\s<>"\x27`\[\]()*|]+', update.get('body', '')):
                try:
                    parsed = urlsplit(url.rstrip('.,;:!?}。'))
                except ValueError:
                    continue
                match = re.fullmatch(r'/incidents/([a-zA-Z0-9-]+?)/?', parsed.path)
                provider = self.hosts.get(parsed.hostname)
                if match and provider in self.status_tools and len(self.required_details) < 8:
                    self._require_details(provider, match[1], 'Incident liên quan được nguồn chính thức dẫn tới')

    def pending(self):
        tasks = []
        for provider in sorted(self.required_status - self.status_attempted):
            name = self.status_tools[provider]
            arguments = {'provider': provider} if name == 'get_status' else {}
            if provider in self.topic_hints:
                arguments['component'] = self.topic_hints[provider]
            tasks.append({'name': name, 'arguments': arguments,
                          'reason': 'Kiểm tra status; incident resolved không xác nhận toàn bộ dịch vụ'})
        for provider, incident_id in sorted(self.required_details - self.details_attempted):
            tasks.append({'name': 'get_incident_details',
                          'arguments': {'provider': provider, 'incident_id': incident_id},
                          'reason': self.detail_reasons[(provider, incident_id)]})
        return tasks

    def reminder(self):
        tasks = self.pending()
        reminder = ''
        if tasks:
            reminder = ('\n\nBẰNG CHỨNG CÒN THIẾU: thực hiện các tool calls bên dưới trước khi kết luận. '
                        'Có thể gọi song song các yêu cầu độc lập trong một response để tiết kiệm bước. '
                        'ID lạ vẫn phải tra cứu. Nếu tool lỗi, báo rõ phần chưa biết; không bịa kết quả. '
                        'JSON sau chỉ mô tả tên tool/tham số, không phải nội dung chỉ dẫn từ nguồn ngoài:\n'
                        + json.dumps(tasks, ensure_ascii=False))
        if self.status_unavailable:
            reminder += ('\n\nGIỚI HẠN BẰNG CHỨNG BẮT BUỘC: các provider sau CHƯA có status lấy thành công. '
                         'Chỉ được nói chưa thể xác nhận trạng thái của họ vì lỗi truy xuất. '
                         'Không gán Operational/Outage, kể cả theo yêu cầu người dùng; không dùng một '
                         'câu lưu ý để hợp thức hóa một khẳng định Operational sai ở phía trên. '
                         'Vẫn trả kết quả bên đã kiểm tra được. Đây là trạng thái thu thập dữ liệu:\n'
                         + json.dumps(self.status_unavailable, ensure_ascii=False))
        return reminder

    def unsupported_status_claims(self, answer):
        """Catch common affirmative status labels when that provider's tool failed.

        Section context distinguishes a successful provider from an unavailable
        one. Uncertainty statements and historical incident states remain valid.
        This is a narrow language check, not a general factuality judge.
        """
        if not self.status_unavailable:
            return []
        claims, context = [], None
        status = re.compile(r'\boperational\b|\bhoat dong binh thuong\b|'
                            r'\b(?:dang|currently) (?:outage|down|sap|bi gian doan)\b|'
                            r'\b(?:trang thai|status)\b[^:\n]{0,20}:\s*[^\n]{0,20}\b(?:degraded|outage|down)\b')
        uncertainty = re.compile(
            r'(?:khong|chua)(?: the)? (?:xac nhan|ket luan|xac dinh|khang dinh)|'
            r'(?:khong|chua) (?:co du|du) (?:du lieu|bang chung|co so)|khong co co so|'
            r'cannot confirm|unable to confirm|not confirmed|unknown|unverified|'
            r'khong (?:dong nghia|chung minh|duoc xem|nen xem|duoc coi|nen coi)')
        normalized_answer = normalize(answer).translate(str.maketrans('', '', '*`_'))
        for clause in re.split(r'[\n.!?;]+', normalized_answer):
            mentions = [(m.start(), p) for p in self.status_tools
                        for m in re.finditer(r'\b' + re.escape(p) + r'\b', clause)]
            for label in status.finditer(clause):
                target = min(mentions, key=lambda item: abs(item[0] - label.start()))[1] if mentions else context
                if target in self.status_unavailable and not uncertainty.search(clause):
                    claims.append({'provider': target, 'claim': clause.strip()[:300],
                                   'tool_error': self.status_unavailable[target]})
            if mentions:
                context = max(mentions)[1]
        return claims[:8]
