"""Tambah sumber NU Online ke proyek (fallback HTML mentah untuk nu.or.id/islam.nu.or.id)."""
import re, sys, html, requests
sys.path.insert(0, r"I:\AG\air-wudhu")
import aw_common as C, aw_research as R

def raw(url):
    h = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>", "\n", h)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", h))
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    txt = "\n".join(l.strip() for l in txt.splitlines() if len(l.strip()) > 2)
    return (html.unescape(t.group(1)).strip() if t else url), txt

def add(pid, urls):
    p = C.load_project(pid)
    have = {s["url"] for s in p["sources"]}
    for u in urls:
        if u in have:
            continue
        try:
            R.add_url(p, u)
            s = p["sources"][0]
            if s["chars"] < 2000 and "nu.or.id" in u:
                raise ValueError("pendek")
        except Exception:
            if p["sources"] and p["sources"][0]["url"] == u:
                p["sources"].pop(0)
            title, txt = raw(u)
            R.add_note(p, title, txt)
            s = p["sources"][0]
            s.update(url=u, domain=R._domain(u), trusted=True)
        print(f"  + {p['sources'][0]['domain']:22} {p['sources'][0]['chars']:6} huruf  {u[-60:]}")
    C.save_project(p)

if __name__ == "__main__":
    add(sys.argv[1], sys.argv[2:])
