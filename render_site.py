import argparse
import ctypes
import html
import json
import os
from collections import Counter
from pathlib import Path
from localization import configure, label as localized_label, text as localized_text

def memory_guard():
    if os.name!='nt':return
    class M(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extended']]
    s=M();s.length=ctypes.sizeof(s)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) or s.available<2*1024**3:
        raise SystemExit('ローカル生成は空き物理メモリ2GiB以上が必要です。GitHub Actionsで生成してください。')

esc=lambda s:html.escape(str(s),quote=True)
show=lambda s:html.escape(localized_text(s),quote=True)
LABELS={}
UPDATED_LABEL='2026年10月28日更新（初回調査：10月27日）'

def val(v,key=''):
    if v is None:return '<span class="muted">未確認</span>'
    if isinstance(v,bool):return 'はい' if v else 'いいえ'
    if isinstance(v,(int,float)):return esc(f'{v:,.0f}円' if 'Jpy' in key or key.startswith('jpy') else v)
    if isinstance(v,str):
        if v.startswith(('https://','http://')) and not any(c.isspace() for c in v):return f'<a href="{esc(v)}" target="_blank" rel="noopener noreferrer">{esc(v)}</a>'
        return '<span class="prose">'+(esc(v) if key=='name' else show(v))+'</span>'
    if isinstance(v,list):return '<ul>'+''.join('<li>'+val(a)+'</li>' for a in v)+'</ul>' if v else '<span class="muted">記載なし</span>'
    if isinstance(v,dict):
        if not v:return '<span class="muted">変更なし</span>'
        rows=[]
        for k,a in v.items():
            if k=='key' and ('title' in v or 'url' in v):continue
            label=localized_label(k)
            if k=='profitAfterOwnerLaborJpy' and v.get('unpricedOperatingCostItems'):label='未見積費用追加前の労働費後残額'
            if k=='observed' and ('paidConversionRateAssumed' in v or 'targetVisitsPerMonth' in v):label='成約率の実測あり'
            rows.append('<dt>'+show(label)+'</dt><dd>'+val(a,k)+'</dd>')
        return '<dl>'+''.join(rows)+'</dl>'
    return esc(v)

def section(title,value):return '<section><h2>'+esc(title)+'</h2>'+val(value)+'</section>'

def page(title,body,total):
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{show(title)}｜訪問で売れる仕事の比較</title><link rel="stylesheet" href="styles.css"></head><body><header><a class="brand" href="index.html">千葉市・車なし・資金1万円の事業比較</a><nav aria-label="資料内"><a href="index.html">全{total}案一覧</a><a href="method.html">結論と比較の前提</a><a href="sources.html">出典・監査</a></nav></header><main>{body}</main><footer>{esc(UPDATED_LABEL)}。件数・費用・利益・訪問成約率は仮説。実訪問・有料受注・利益の実測は未実施。</footer></body></html>'''

def main():
    global UPDATED_LABEL
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='public-catalog.json')
    parser.add_argument('--output',default='_site')
    args=parser.parse_args()
    memory_guard()
    catalog=json.loads(Path(args.input).read_text(encoding='utf-8'))
    UPDATED_LABEL=catalog['metadata']['dateLabel']
    data=catalog['businesses'];total=len(data);new=[x for x in data if x.get('isNew')]
    assert total==130 and len(new)==30
    assert {x['id'] for x in data}==set(range(1,131))
    assert {x['id'] for x in new}==set(range(101,131))
    assert all(len(x['debates'])==x['debateRoundsCompleted'] for x in data)
    assert catalog['audit']['passed']
    LABELS.update(catalog['labels'])
    configure(catalog['labels'],catalog['phrases'])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'styles.css').write_text(catalog['styles'],encoding='utf-8')
    new_tag='<span class="new" aria-label="今回追加した案">新規</span>'
    ranked=sorted(data,key=lambda x:(-int(bool(x.get('isNew'))),-x.get('doorVisitFit',{}).get('score',0),-x['overallScore'],x['id']))
    rows=[]
    for i,x in enumerate(ranked,1):
        visit=x.get('doorVisitFit',{}).get('score')
        score=f'{visit}/5' if visit is not None else '今回未採点'
        badge=new_tag if x.get('isNew') else ''
        search=localized_text(x['name']+' '+x['customer']+' '+str(x['job']))
        rows.append(f'<tr data-search="{esc(search)}" data-fit="{esc(x["startup"]["fitNow"])}" data-new="{int(bool(x.get("isNew")))}" data-visit="{visit or 0}" data-score="{x["overallScore"]}" data-id="{x["id"]}"><td class="num order">{i}</td><td><a href="business-{x["id"]:03}.html">{show(x["name"])}</a> {badge}<br><small>案{x["id"]}</small></td><td class="num">{x["overallScore"]:.0f}</td><td>{score}</td><td>{esc(x["startup"]["fitNow"])}</td></tr>')
    picks=[]
    by_id={x['id']:x for x in data}
    for n in catalog['preferences'].get('suggestedNewIds',[]):
        x=by_id[n];assert x.get('isNew')
        picks.append(f'<a href="business-{n:03}.html">{show(x["name"])}</a>')
    intro='<h1>訪問して売れる仕事の比較</h1><p class="lead">既存100案に、清掃以外の戸別訪問・小作業・配布を30案追加しました。</p><p>追加案には '+new_tag+' を付け、先頭に表示しています。<b>「新規30案だけ」</b>で絞り込めます。各案を押すと市場・料金・収支・競合・検討履歴が読めます。</p>'
    if picks:intro+='<p>先に条件を確かめる候補：'+' ／ '.join(picks)+'。有料需要や1万円以内の開始が確認済みという意味ではありません。</p>'
    intro+='<p>訪問適合は、家庭へ作業を提案しやすいか、または依頼主から仕事を受けて各戸を回れるかの追加評価です。<a href="method.html">評価の違いと営業時間の考え方</a>を確認してください。清掃中心の旧評価を、今回の着手順にはしていません。</p>'
    intro+='<p>以前の案にある<a href="business-001.html">草むしり（案1）</a>と<a href="business-079.html">チラシ配布（案79）</a>も残しています。この2案は今回の新規30案には数えていません。</p>'
    intro+='<div class="tools"><label>名称・顧客を検索<input id="search" type="search" placeholder="包丁、交換、配布 など"></label><label>本人条件<select id="fit"><option value="">すべて</option><option>条件付</option><option>将来</option><option>見送り</option></select></label><label class="checkbox"><input id="new-only" type="checkbox">新規30案だけ</label><label>表示順<select id="sort"><option value="new">新規案 → 訪問適合</option><option value="score">総合点</option><option value="visit">訪問適合</option><option value="id">案番号</option></select></label></div>'
    intro+=f'<p id="count" aria-live="polite">{total}案を表示／{total}案</p><div class="table-wrap"><table><thead><tr><th>表示順</th><th>事業案</th><th>総合点 / 100</th><th>訪問適合</th><th>本人条件</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><script src="filter.js" defer></script>'
    (out/'index.html').write_text(page('全130案一覧',intro,total),encoding='utf-8')
    filter_js='''const rows=[...document.querySelectorAll('tbody tr')];const body=document.querySelector('tbody');const total=rows.length;function render(){const q=document.getElementById('search').value.trim().toLowerCase();const fit=document.getElementById('fit').value;const onlyNew=document.getElementById('new-only').checked;const sort=document.getElementById('sort').value;rows.sort((a,b)=>sort==='id'?+a.dataset.id-+b.dataset.id:sort==='score'?+b.dataset.score-+a.dataset.score||+a.dataset.id-+b.dataset.id:sort==='visit'?+b.dataset.visit-+a.dataset.visit||+b.dataset.score-+a.dataset.score:+b.dataset.new-+a.dataset.new||+b.dataset.visit-+a.dataset.visit||+b.dataset.score-+a.dataset.score||+a.dataset.id-+b.dataset.id);let n=0;for(const r of rows){r.hidden=!(r.dataset.search.toLowerCase().includes(q)&&(!fit||r.dataset.fit===fit)&&(!onlyNew||r.dataset.new==='1'));if(!r.hidden){n++;r.querySelector('.order').textContent=n}body.append(r)}document.getElementById('count').textContent=n+'案を表示／'+total+'案'}document.getElementById('search').addEventListener('input',render);for(const id of ['fit','new-only','sort'])document.getElementById(id).addEventListener('change',render);render();'''
    (out/'filter.js').write_text(filter_js,encoding='utf-8')
    keys={'id','name','category','customer','job','market','pricing','unitEconomics','startup','competitors','selfAlternative','diyAlternative','acquisition','repeat','scalePath','risks','regulatory','validation','scores','agentScores','rootCalibration','scoreRationale','scoreReason','sourceUrls','verdict','researchDate','debateRoundsCompleted','debateCompletedRounds','overallScore','debates','sensitivity','reviewFindings','reviewDecisions','isNew','addedOn','newComparedTo','doorVisitFit','doorSalesModel','doorWorkType','zeroExistingCustomerScenario'}
    for x in data:
        n=x['id'];badge=new_tag if x.get('isNew') else ''
        body=f'<p><a href="index.html">← 全{total}案一覧へ</a></p><h1><small>案{n}</small> {badge}<br>{show(x["name"])}</h1><p><span class="pill">{x["overallScore"]:.0f}点 / 100</span> <span class="pill">{esc(x["startup"]["fitNow"])}</span></p>'
        body+=section('最終判断',x['verdict'])
        if x.get('isNew'):
            route='依頼主から受託して各戸を回る仕事' if x.get('doorWorkType')=='commissioned-route' else '家庭へ作業を提案する仕事'
            body+='<p class="notice">今回追加した案です。'+route+'として評価。訪問適合の高さは、技能・初回資金・実受注の確認済みを意味しません。</p>'
            body+=section('訪問で売る場合の適合',x['doorVisitFit'])+section('訪問営業・受託獲得の試算',x['doorSalesModel'])+section('既存案との違い・重なる市場',x['newComparedTo'])
            body+=section('既存客ゼロから始める月の仮説',x['zeroExistingCustomerScenario'])
        for title,value in [('顧客と作業範囲',{'支払う顧客':x['customer'],'提供する作業':x['job']}),('本人条件と初期資金',x['startup']),('市場の広さ',x['market']),('料金と収益モデル',x['pricing']),('月次シナリオの仮試算',x['unitEconomics']),('値下げ・受注減・雇用の比較',x['sensitivity'])]:body+=section(title,value)
        body+='<p class="notice">受注件数・成約率・費用・利益は仮説です。本人全時間1,500円/時、代替労働2,500円/時＋追加管理5万円を比較。月次に既存顧客や継続を含む場合、ゼロからの初月と混ぜません。未見積運営費がある案の全費用後利益は未確定です。税・社会保険等を引いた手取りではありません。</p>'
        for title,key in [('代表競合と参入余地','competitors'),('顧客の自力代替','selfAlternative'),('集客','acquisition'),('継続性','repeat'),('拡大する順序','scalePath'),('リスク','risks'),('登録・法令等の条件','regulatory'),('最初14日の検証','validation'),('採点の内訳','scores'),('採点理由と統合補正','scoreRationale'),('出典','sourceUrls')]:body+=section(title,x.get(key))
        extra={k:v for k,v in x.items() if k not in keys}
        if extra:body+='<details><summary>追加検討で定めた条件</summary>'+val(extra)+'</details>'
        body+=f'<section><h2>{len(x["debates"])}回の指摘と回答</h2><p class="muted">当時の条件と旧数値も残す履歴です。現在の判断は上の最終本文を参照してください。討論は実需要の証明ではありません。項目名や内部記号は日本語表示に置き換えています。</p>'
        for z in x['debates']:
            r=z['review']['round']
            body+=f'<details class="debate" data-round="{r}"><summary>第{r}回　{show(z["review"].get("focus","検討"))}</summary><h3>別担当の指摘</h3>'+val(z['review'])+'<h3>所有担当の回答</h3>'+val(z['response'])+'</details>'
        body+='</section><div class="paging">'
        if n>1:body+=f'<a href="business-{n-1:03}.html">← 案{n-1}</a>'
        body+='<a href="index.html">一覧へ</a>'
        if n<total:body+=f'<a href="business-{n+1:03}.html">案{n+1} →</a>'
        body+='</div>'
        (out/f'business-{n:03}.html').write_text(page(x['name'],body,total),encoding='utf-8')
    method='<h1>今回の希望と評価の読み方</h1>'
    for paragraph in catalog['methodParagraphs']:method+='<p>'+esc(paragraph)+'</p>'
    method+=section('追加30案の訪問適合',catalog['visitMethod'])
    method+='<section><h2>訪問して提案する際の前提</h2><p>契約の勧誘に先立つ事業者・目的・役務の明示、拒否された相手への再勧誘禁止、法定書面、解除制度などを収支と実施条件へ含めています。その日に作業しただけで代金が確定すると扱いません。具体的な例外の適用は個別確認が必要です。<a href="https://www.no-trouble.caa.go.jp/what/doortodoorsales/" target="_blank" rel="noopener noreferrer">消費者庁の訪問販売ガイド</a></p></section>'
    if catalog.get('previousMethodHtml'):method+='<details><summary>前回100案の結論・拡大モデル（当時の評価）</summary>'+catalog['previousMethodHtml']+'</details>'
    (out/'method.html').write_text(page('結論と比較の前提',method,total),encoding='utf-8')
    sources='<h1>出典と監査</h1>'+section('全体監査',catalog['audit'])+'<p>記録と算術の検査で、現地需要や採算の成立を保証する検査ではありません。</p>'+section('横断して確認した資料',catalog['sources'])+'<details><summary>各担当の出典一覧と確認方法</summary>'+val(catalog['sourceLedger'])+'</details>'
    (out/'sources.html').write_text(page('出典と監査',sources,total),encoding='utf-8')
    (out/'.nojekyll').write_text('',encoding='utf-8')
    print(json.dumps({'businesses':total,'new':len(new),'debatePairs':sum(len(x['debates']) for x in data),'fitCounts':dict(Counter(x['startup']['fitNow'] for x in data))},ensure_ascii=False))

if __name__=='__main__':main()
