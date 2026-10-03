import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

root=Path.cwd()
evidence=root/'.local/decoder-auto-mfsk32'
output=evidence/'nondefault-8khz-control'
spec=importlib.util.spec_from_file_location('grampy._dispatch_baseline',evidence/'baseline-source/pipeline.py')
baseline=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=baseline
spec.loader.exec_module(baseline)
started=time.perf_counter()
recording=baseline.SigmfRecording.open(output/'broadcast.sigmf-meta',output/'broadcast.sigmf-data',start_sample=None,stop_sample=None)
acquisition=baseline.acquire_modes(recording)
config=baseline.DecodeConfig()
decoded_modes,warnings=baseline._decode_automatic_text(recording,acquisition,config,run_wall_start=started)
text32=next(item for item in decoded_modes if item.mode_segment['mode']=='MFSK32')
directory=output/'existing-mfsk32-path'
directory.mkdir()
pictures=baseline._decode_bounded_pictures(recording,text32,mode='MFSK32',artifact_dir=directory/'artifacts',
    artifact_path_prefix='artifacts',run_wall_start=started,component_estimator=config.picture_component_estimator,
    component_window=config.picture_component_window,filter_profile=config.picture_filter_profile,
    boundary_estimator=config.picture_boundary_estimator,range_config=None)
candidate=json.loads((output/'candidate/diagnostic.json').read_text())
old_artifacts={item['id']:item for item in pictures.artifacts}
new_artifacts={item['id']:item for item in candidate['artifacts']}
new_pictures=[item for item in candidate['pictures'] if item['mode']=='MFSK32']
assert len(pictures.pictures)==len(new_pictures)==2
matches=[]
for old,new in zip(pictures.pictures,new_pictures):
    old_image=np.asarray(Image.open(directory/old_artifacts[old['raster_artifact']]['path']))
    new_image=np.asarray(Image.open(output/'candidate'/new_artifacts[new['raster_artifact']]['path']))
    matches.append(np.array_equal(old_image,new_image))
assert all(matches)
record=json.loads((evidence/'nondefault-8khz-control.json').read_text())
record['existing_mfsk32_path_pixel_identical']=matches
record['interpretation']='Nondefault 8-kHz mixed fixture is outside the frozen 48-kHz matrix. Its MFSK64 defect occurs in the retained automatic baseline, and both MFSK32 rasters match the pre-change bounded picture algorithm exactly. These existing quality limitations are not repaired by this dispatch correction.'
(evidence/'nondefault-8khz-control.json').write_text(json.dumps(record,indent=2)+'\n')
(root/'docs/decoder/data/auto-mfsk32-pictures/nondefault-8khz-control.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
