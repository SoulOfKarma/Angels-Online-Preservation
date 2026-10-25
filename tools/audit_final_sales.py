"""Read final IGG Mall announcements and enumerate matching local products."""
import pathlib,sys,json,re,urllib.request,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8')
from mall_selection import items,name,drop_rows
def fetch(aid):
    url='https://ao.igg.com/news/news.php?aid='+str(aid)
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    try:
        data=urllib.request.urlopen(request,timeout=12).read().decode('utf8','replace')
        folder=ROOT/'scratch/final_sales';folder.mkdir(parents=True,exist_ok=True)
        (folder/('%d.html'%aid)).write_text(data,encoding='utf8')
        text=re.sub('<[^>]+>',' ',data);text=re.sub(r'\s+',' ',text)
        start=text.find('Issued On:')
        return url,text[start:start+18000]
    except Exception as exc:return url,type(exc).__name__+': '+str(exc)
if '--fetch' in sys.argv:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(fetch,(5544,5532,5528)):print(*result,sep='\n')
else:
    table=items();drops=drop_rows()
    if '--roots' in sys.argv:
        for i in (82270,82408,82660):
            r=table[i];d=drops.get(int(r.get('\u52d5\u614b\u8cc7\u65991') or 0),{})
            print(i,name(r),[(int(d['item%d'%n]),name(table.get(int(d['item%d'%n]),{}))) for n in range(1,41) if d.get('item%d'%n)])
        sys.exit()
    for i,r in sorted(items().items()):
        if i>=80000 and re.search('egg|bubble|lucky bag',name(r),re.I) and r.get('\u4e0d\u53ef\u4ea4\u6613')!='\u662f' and r.get('\u4e0d\u53ef\u5b58\u5009\u5eab')!='\u662f':
            print(i,name(r),r.get('\u7269\u54c1\u985e\u5225'),r.get('\u52d5\u614b\u8cc7\u65991'))
