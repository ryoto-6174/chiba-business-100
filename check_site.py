import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

class Inspect(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.rounds=[];self.rows=[];self.in_dt=False;self.dt_texts=[];self.current_dt='';self.in_badge=False;self.badges=[];self.current_badge=''
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('a','link') and a.get('href'):self.links.append(a['href'])
        if tag=='script' and a.get('src'):self.links.append(a['src'])
        if tag=='details' and 'data-round' in a:self.rounds.append(int(a['data-round']))
        if tag=='tr' and 'data-id' in a:self.rows.append(a)
        if tag=='dt':self.in_dt=True;self.current_dt=''
        if tag=='span' and a.get('class')=='new':self.in_badge=True;self.current_badge=''
    def handle_data(self,data):
        if self.in_dt:self.current_dt+=data
        if self.in_badge:self.current_badge+=data
    def handle_endtag(self,tag):
        if tag=='dt' and self.in_dt:self.dt_texts.append(self.current_dt);self.in_dt=False
        if tag=='span' and self.in_badge:self.badges.append(self.current_badge);self.in_badge=False

def main():
    inp=Path(sys.argv[1]);out=Path(sys.argv[2])
    catalog=json.loads(inp.read_text(encoding='utf-8'))
    data=catalog['businesses'];ids={x['id'] for x in data}
    assert ids==set(range(1,131)) and len(data)==130
    assert {x['id'] for x in data if x.get('isNew')}==set(range(101,131))
    assert catalog['audit']['passed']
    assert catalog['audit']['businessCount']==130
    expected_pairs=sum(len(x['debates']) for x in data)
    assert catalog['audit']['reviewCount']==catalog['audit']['responseCount']==expected_pairs
    index=Inspect();index.feed((out/'index.html').read_text(encoding='utf-8'))
    assert len(index.rows)==130
    assert {int(r['data-id']) for r in index.rows if r['data-new']=='1'}==set(range(101,131))
    assert all(r['data-new']=='1' for r in index.rows[:30])
    assert index.badges and all(s=='新規' for s in index.badges)
    assert 'id="new-only"' in (out/'index.html').read_text(encoding='utf-8')
    assert (out/'filter.js').is_file()
    all_rounds=0;broken=[];secret_findings=[];english_labels=[]
    forbidden={
        'github_token':r'(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}',
        'stripe_secret':r'sk_(?:live|test)_[A-Za-z0-9]{16,}',
        'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'local_path':r'(?:[A-Z]:[\\/]Users[\\/]|file://|127\.0\.0\.1|localhost)',
    }
    for x in data:
        f=out/f'business-{x["id"]:03}.html'
        t=f.read_text(encoding='utf-8');p=Inspect();p.feed(t)
        assert p.rounds==list(range(1,len(x['debates'])+1)),f.name
        assert ('class="new"' in t)==bool(x.get('isNew')),f.name
        all_rounds+=len(p.rounds)
    for f in out.iterdir():
        if not f.is_file():continue
        t=f.read_text(encoding='utf-8')
        for name,pat in forbidden.items():
            if re.search(pat,t,re.I):secret_findings.append({'file':f.name,'type':name})
        if f.suffix!='.html':continue
        p=Inspect();p.feed(t)
        english_labels.extend({'file':f.name,'label':s} for s in p.dt_texts if re.search(r'[A-Za-z]',s))
        for link in p.links:
            u=urlsplit(link)
            if not u.scheme and u.path and not (out/u.path).is_file():broken.append([f.name,link])
    assert all_rounds==expected_pairs
    assert not broken,broken
    assert not secret_findings,secret_findings
    assert not english_labels,english_labels[:20]
    result={'businesses':130,'new':30,'newIds':list(range(101,131)),'debatePairs':all_rounds,'roundsByBusiness':{str(x['id']):len(x['debates']) for x in data},'brokenLocalLinks':broken,'secretOrLocalPathFindings':secret_findings,'englishFieldLabels':english_labels,'newBadge':'新規','publicCatalogSha256':hashlib.sha256(inp.read_bytes()).hexdigest(),'indexBytes':(out/'index.html').stat().st_size,'maxBusinessPageBytes':max(f.stat().st_size for f in out.glob('business-*.html')),'files':[{'name':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(out.iterdir()) if f.is_file()]}
    Path('site-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
