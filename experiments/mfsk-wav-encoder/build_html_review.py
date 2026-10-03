"""Build a portable human review page from preserved Session 8 artifacts."""
import base64
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def png_data(image):
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


root = Path(sys.argv[1])
output = Path(sys.argv[2])
diagnostics = json.loads((root/'visual-review/diagnostic-results.json').read_text())
manifest = json.loads((root/'qualification-manifest.json').read_text())
rows = []
for record in diagnostics:
    name, speed = record['case'], record['speed']
    color = 'grayscale' if 'grayscale' in name else 'RGB'
    truth = Image.open(root/'inputs/primary-color-8x4.png').convert('RGB')
    if color == 'grayscale':
        array = np.asarray(truth, dtype=np.uint16)
        truth = Image.fromarray(((31*array[:,:,0]+61*array[:,:,1]+8*array[:,:,2])//100).astype(np.uint8))
    grampy = Image.open(root/f'visual-review/{name}-p{speed}-grampy.png').convert(truth.mode)
    fldigi = Image.open(root/record['reference']).convert(truth.mode)
    def stats(image):
        errors = np.abs(np.asarray(image,dtype=np.int16)-np.asarray(truth,dtype=np.int16))
        return {'max':int(errors.max()),'mae':float(errors.mean()),'different':int(np.count_nonzero(errors)),
                'total':int(errors.size)}
    sources = [truth, grampy, fldigi]
    images = [{'url':png_data(im),'pixels':np.asarray(im.convert('RGB')).reshape(-1,3).tolist()} for im in sources]
    rows.append({'case':name,'speed':speed,'color':color,'images':images,'grampy':stats(grampy),
                 'fldigi':stats(fldigi),'image_name':Path(record['reference']).name,
                 'log':f'attempt2/cases/{name}/received/fldigi/control.log',
                 'text':f'attempt2/cases/{name}/received/decoded.txt',
                 'metadata':f'attempt2/cases/{name}/received/metadata.json'})
payload = json.dumps(rows).replace('<','\\u003c')
template = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Session 8 · Human picture review</title><style>
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,sans-serif;background:#f3f5f8;color:#172334}
header,main{max-width:1450px;margin:auto;padding:24px}header h1{margin:0 0 8px;font-size:30px}
.note{background:#fff2df;border-left:4px solid #d28017;padding:14px 18px;margin:16px 0}
.toolbar{display:flex;gap:24px;align-items:center;flex-wrap:wrap;background:white;padding:14px;border-radius:10px;position:sticky;top:0;z-index:2}
select,button{font:inherit;padding:6px 12px}section{background:white;margin:22px 0;padding:22px;border-radius:12px;box-shadow:0 2px 8px #1623340a}
h2{font-size:20px;margin:0 0 12px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;overflow:auto}
.panel{min-width:240px}.panel h3{font-size:15px;margin:4px 0 8px}.panel img{display:block;width:var(--zoom,256px);max-width:100%;height:auto;image-rendering:pixelated;outline:1px solid #aab4c0;background:#ddd}
.placeholder{height:128px;background:#eef1f5;padding:18px;font-size:14px;color:#627082}.metrics{font-size:13px;margin-top:12px}.fail{color:#a43b24;font-weight:650}.good{color:#24643d}.small{font-size:14px;color:#536071}
.pixel{margin:16px 0 0;padding:10px;background:#eef3f9;font-family:ui-monospace,monospace;font-size:13px;min-height:40px}
a{color:#2359a4}details{background:#fff;padding:16px;border-radius:10px;margin-top:16px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;text-align:left;border-bottom:1px solid #ddd}
@media(max-width:850px){.grid{grid-template-columns:repeat(4,260px)}header,main{padding:15px}}
</style></head><body><header><h1>Session 8 · Human picture review</h1>
<p>Known original → GramPy recovery → pinned fldigi autosaved PNG. Seven received images, all 8 × 4 pixels.</p>
<div class="note"><b>Qualification remains failed for these three picture cases.</b> Mode acquisition and ordered text passed. These are saved receiver artifacts; a fldigi harness or save-path defect remains possible. GramPy recovery uses known boundaries and carrier hints and is diagnostic evidence.</div>
<p class="small">Pixels are enlarged without smoothing. Hover over any image to compare the same pixel across all three images. No accepted encoder baseline exists for this new feature.</p>
<details><summary>What was the same as decoder qualification, and what changed?</summary>
<table><tr><th>Item</th><th>Archived qualification</th><th>Session 8 corrected run</th></tr>
<tr><td>Receiver binary</td><td>fldigi 4.2.13, pinned dd30f86c…966f3</td><td>Same verified binary</td></tr>
<tr><td>Adapter and audio path</td><td>fldigi-decode-wav; ALSA loopback; plug capture</td><td>Same path; archived control.py and asound.conf hashes match Session 8 exactly</td></tr>
<tr><td>Initial mode</td><td>Fixture-specific; MFSK64 for small-image cases</td><td>BPSK31, automatic RxID acquisition</td></tr>
<tr><td>Receiver configuration</td><td>Generated by adapter</td><td>Explicit fresh configuration; corrected AUDIOIO=1; wide RxID search</td></tr>
<tr><td>Polling / wait</td><td>Default polling; 15-second post-playback wait</td><td>Requested 0.25-second polling (adapter clamps to 0.5); same wait</td></tr>
<tr><td>Historical assertions</td><td>Expected text, minimum picture count, no RPC refusal</td><td>Also exact geometry and pixel comparisons</td></tr>
</table><p class="small">The historical full adapter was not archived here, so its complete byte identity is unproven. Runtime configurations differ as listed above.</p>
<div class="note"><b>Historical qualification warning:</b> its saved grayscale PNG could not be decoded by Pillow. Its RGB image is readable but differs from the current known original. The old checks asserted picture counts, not exact geometry or pixels. These archived artifacts strengthen the case for investigating the shared save path; they do not prove a cause. <a href="harness-audit.md">Harness audit and preserved evidence</a>.</div>
</details></header><main>
<div class="toolbar"><label>Show <select id="filter"><option value="all">All seven images</option><option value="grayscale">Grayscale</option><option value="RGB">RGB</option><option value="2">p2</option><option value="4">p4</option><option value="8">p8</option></select></label>
<label>Pixel enlargement <input id="zoom" type="range" min="128" max="512" step="32" value="256"></label><span id="count">7 images</span>
<a href="attempt2/qualification-manifest.json">Qualification manifest</a><a href="README.md">Evidence index</a></div>
<div id="rows"></div></main><script id="data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent), container=document.getElementById('rows');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const metric=(s,label)=>`<div class="metrics"><b>${label}</b><br>Max component error: ${s.max}<br>Mean absolute error: ${s.mae.toFixed(2)}<br>Unequal components: ${s.different} / ${s.total}</div>`;
data.forEach((r,i)=>{
const section=document.createElement('section');section.dataset.color=r.color;section.dataset.speed=r.speed;
section.innerHTML=`<h2>${esc(r.case)} · ${esc(r.color)} · p${r.speed}</h2><div class="grid">
<div class="panel"><h3>Original truth</h3><img data-index="0" src="${r.images[0].url}" alt="Original"><div class="metrics">8 × 4 · exact expected pixels</div></div>
<div class="panel"><h3>Accepted encoder baseline</h3><div class="placeholder">Unavailable: new encoder feature.</div></div>
<div class="panel"><h3>GramPy recovery · diagnostic</h3><img data-index="1" src="${r.images[1].url}" alt="GramPy decoded image">${metric(r.grampy,'Not pixel-exact')}</div>
<div class="panel"><h3>Pinned fldigi · saved PNG</h3><img data-index="2" src="${r.images[2].url}" alt="fldigi saved image">${metric(r.fldigi,'Pixel check failed')}</div></div>
<div class="pixel">Hover over a pixel to inspect RGB values and differences.</div><p class="small">Saved artifact: ${esc(r.image_name)} · <a href="${r.log}">Receiver log</a> · <a href="${r.text}">Decoded text</a> · <a href="${r.metadata}">Receiver configuration and metrics</a></p>`;
section.querySelectorAll('img').forEach(img=>img.addEventListener('mousemove',e=>{const b=img.getBoundingClientRect();const x=Math.min(7,Math.max(0,Math.floor((e.clientX-b.left)/b.width*8))),y=Math.min(3,Math.max(0,Math.floor((e.clientY-b.top)/b.height*4)));const values=r.images.map(im=>im.pixels[y*8+x]);const delta=v=>v.map((c,j)=>c-values[0][j]);section.querySelector('.pixel').textContent=`Pixel (${x}, ${y}) · truth ${values[0]} · GramPy ${values[1]} [Δ ${delta(values[1])}] · fldigi ${values[2]} [Δ ${delta(values[2])}]`;}));container.appendChild(section);
});
document.getElementById('filter').addEventListener('change',e=>{let n=0;container.querySelectorAll('section').forEach(s=>{const show=e.target.value==='all'||s.dataset.color===e.target.value||s.dataset.speed===e.target.value;s.hidden=!show;if(show)n++;});document.getElementById('count').textContent=`${n} images`;});
document.getElementById('zoom').addEventListener('input',e=>document.documentElement.style.setProperty('--zoom',e.target.value+'px'));
</script></body></html>'''
output.write_text(template.replace('__DATA__',payload))
print(f'Saved {output}: {len(rows)} images, self-contained pixel data')
