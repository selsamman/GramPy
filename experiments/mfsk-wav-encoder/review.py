"""Candidate-set review; local recovery uses known boundaries as diagnostics."""
import json, pathlib, sys, wave
import numpy as np
from scipy import signal
from PIL import Image, ImageDraw
from grampy.mfsk_segment_encode import ImageSource, plan_mfsk_segment
from grampy.text_decode import decode_mfsk_text
from grampy.picture_decode import decode_pictures
root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else '.local/session8/evidence')
review=root/'visual-review';review.mkdir(exist_ok=True)
rows=[];results=[]
for name in ['rsid-mixed-audio-silence-picture','mfsk32-grayscale-speeds','mfsk64-color-speeds']:
 d=root/'cases'/name
 composition=json.loads((d/'composition.json').read_text())
 record=json.loads((d/'encoder-result.json').read_text())
 images=sorted((d/'received/images').glob('*'))
 with wave.open(str(d/'generated.wav')) as w: real=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/16384
 received_index=0
 for index,p in enumerate(composition):
  if p['kind']!='mfsk' or not any(c['kind']=='image' for c in p['contents']):continue
  contents=[c['utf8'].encode() if c['kind']=='text' else ImageSource(root/'inputs/primary-color-8x4.png',c['color'],c['samples_per_pixel']) for c in p['contents']]
  plan=plan_mfsk_segment(contents=contents,mode=p['mode'],carrier_hz=p['carrier_hz'],sample_rate_hz=48000)
  start=record['segments_frames'][index]['start_frame']+(111450 if p['mode']=='MFSK32' else 222900)
  analytic=signal.hilbert(real[start:start+plan.frame_count]).astype(np.complex64)
  prefix_start=0
  image_parts=[c for c in p['contents'] if c['kind']=='image']
  for image_index,(transition,c) in enumerate(zip(plan.picture_transitions,image_parts)):
   prefix=decode_mfsk_text(analytic[prefix_start:transition.prologue_start_frame],input_start=prefix_start,sample_rate=48000.,orientation_hint='normal',trace_level='events',mode=p['mode'],center_hint_hz=p['carrier_hz'])
   decoded=decode_pictures(analytic,input_start=0,sample_rate=48000,mode=p['mode'],orientation='normal',center_hz=p['carrier_hz'],text_events=prefix.text_events)
   candidate=None
   for art in decoded.artifacts:
    values=art.get('values',[])
    if len(values) >= (96 if c['color']=='color' else 32):
     array=np.array(values,dtype=np.uint8)
     array=array.reshape(art['shape'])
     candidate=Image.fromarray(array)
     break
   truth=Image.open(root/'inputs/primary-color-8x4.png').convert('RGB')
   if c['color']=='grayscale':
    rgb=np.array(truth,dtype=np.uint16);truth=Image.fromarray(((31*rgb[:,:,0]+61*rgb[:,:,1]+8*rgb[:,:,2])//100).astype(np.uint8))
   reference=Image.open(images[received_index]).convert(truth.mode);received_index+=1
   label=f"{name} / p{c['samples_per_pixel']}"
   candidate_path=review/f'{name}-p{c["samples_per_pixel"]}-grampy.png'
   if candidate is not None:candidate.save(candidate_path)
   results.append({'case':name,'speed':c['samples_per_pixel'],'candidate_recovery':candidate is not None,'candidate_pixel_exact':candidate is not None and candidate.tobytes()==truth.tobytes(),'reference':str(images[received_index-1].relative_to(root))})
   rows.append((label,truth,candidate,reference))
   prefix_start=transition.post_picture_flush_start_frame
canvas=Image.new('RGB',(1440,100+130*len(rows)), 'white');draw=ImageDraw.Draw(canvas)
for col,label in enumerate(['Truth','Accepted encoder baseline: none','Candidate: GramPy recovery (coupled)','Pinned fldigi received artifact']):draw.text((col*360+10,20),label,fill='black')
for i,(label,truth,candidate,reference) in enumerate(rows):
 y=75+i*130;draw.text((10,y),label,fill='black')
 for col,img in [(0,truth),(2,candidate),(3,reference)]:
  if img is None:draw.text((col*360+10,y+45),'No local recovery',fill='red');continue
  enlarged=img.convert('RGB').resize((240,80),Image.Resampling.NEAREST);canvas.paste(enlarged,(col*360+10,y+25))
 draw.text((370,y+45),'New feature; no accepted encoder output',fill='gray')
canvas.save(review/'candidate-set-review.png')
(review/'diagnostic-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
