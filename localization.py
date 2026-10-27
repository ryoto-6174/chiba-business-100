import re

LABELS={}
PHRASES={}
_ALIASES=None
_URL=re.compile(r"(https?://[^\s<>]+)")

def configure(labels,phrases):
    global _ALIASES
    LABELS.clear();LABELS.update(labels)
    PHRASES.clear();PHRASES.update(phrases)
    aliases={k:v for k,v in LABELS.items() if len(k)>2 and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',k)}
    aliases.update({k:v for k,v in PHRASES.items() if len(k)>1})
    _ALIASES=(re.compile(r'(?<![A-Za-z0-9_])('+ '|'.join(re.escape(k) for k in sorted(aliases,key=len,reverse=True))+r')(?![A-Za-z_])'),aliases) if aliases else None

def raw_label(key):
    if key in LABELS:return LABELS[key]
    m=re.fullmatch(r'r0*(\d{1,2})',key)
    if m:return f'第{int(m[1])}回'
    if '.' in key:
        try:return '・'.join(raw_label(k) for k in key.split('.'))
        except KeyError:pass
    if not re.search(r'[A-Za-z]',key):return key
    raise KeyError('日本語表示名が未定義: '+key)

def _fragment(s):
    s=re.sub(r'/root/(field|add)_([abc])',lambda m:('元調査の' if m[1]=='field' else '追加調査の')+{'a':'第一担当','b':'第二担当','c':'第三担当'}[m[2]],s)
    s=re.sub(r'garden-waste-chiba-(?:note|注記)\.json','千葉市の草木処理条件の確認記録',s)
    s=re.sub(r'(reviews|responses)-(add_)?([abc])-r(\d+)\.json',lambda m:('追加調査の' if m[2] else '')+{'a':'第一担当','b':'第二担当','c':'第三担当'}[m[3]]+f'・第{int(m[4])}回の'+('指摘記録' if m[1]=='reviews' else '回答記録'),s)
    s=re.sub(r'batch-(add_)?([abc])\.json',lambda m:('追加調査の' if m[1] else '')+{'a':'第一担当','b':'第二担当','c':'第三担当'}[m[2]]+'の事業データ',s)
    def path(match):
        try:return raw_label(match[0])
        except KeyError:return match[0]
    s=re.sub(r'(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+(?![A-Za-z0-9_])',path,s)
    if _ALIASES:
        pattern,aliases=_ALIASES
        s=pattern.sub(lambda m:aliases[m[0]],s)
    s=re.sub(r'(?<![A-Za-z0-9])r0*(\d{1,2})(?![A-Za-z0-9])',lambda m:f'第{int(m[1])}回',s)
    s=re.sub(r'(?<=\d)\s*h(?![A-Za-z])','時間',s)
    s=re.sub(r'(?<=\d)\s*min(?![A-Za-z])','分',s)
    return s

def text(value):
    s=str(value)
    s=PHRASES.get(s,LABELS.get(s,s))
    m=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})(?: JST)?',s)
    if m:return f'{m[1]}年{int(m[2])}月{int(m[3])}日'+('（日本時間）' if s.endswith(' JST') else '')
    return ''.join(part if part.startswith(('https://','http://')) else _fragment(part) for part in _URL.split(s))

def label(key):return text(raw_label(key))
