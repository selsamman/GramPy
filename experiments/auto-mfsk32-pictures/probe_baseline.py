from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from grampy.api import DecodeConfig, EncodeConfig, decode_iq_products, encode_mfsk_wav

root=Path.cwd()
evidence=root/'.local/decoder-auto-mfsk32'
spec=importlib.util.spec_from_file_location('grampy._dispatch_baseline',evidence/'baseline-source/pipeline.py')
baseline=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=baseline
spec.loader.exec_module(baseline)
rows=[]
for case in json.loads((root/'.local/session9/practical/prepared.json').read_text())['cases']:
    if case['mode'] != 'MFSK32':
        continue
    source=root/'.local/session9/practical/cases'/case['id']
    output=evidence/'fixed-center-baseline'/case['id']
    output.mkdir(parents=True)
    manifest=baseline.run_reference_pipeline(meta_path=source/'grampy/input.sigmf-meta',data_path=source/'grampy/input.sigmf-data',
         start_sample=None,stop_sample=None,config=baseline.DecodeConfig(mode='MFSK32',center_hz=1500),
         artifact_dir=output/'artifacts',artifact_path_prefix='artifacts')
    (output/'diagnostic.json').write_text(json.dumps(manifest,indent=2)+'\n')
    images=[item for item in manifest['artifacts'] if item['kind']=='png_uint8_raster']
    row={'id':case['id'],'pictures':len(images),'explicit_center_hz':1500}
    if len(images)==1:
        truth=np.asarray(Image.open(source/'truth.png')).astype(float)
        observed=np.asarray(Image.open(output/images[0]['path'])).astype(float)
        row['raw_mae_255']=float(np.mean(np.abs(observed-truth)))
    rows.append(row)
    print(json.dumps(row),flush=True)
(evidence/'fixed-center-baseline.json').write_text(json.dumps(rows,indent=2)+'\n')

# Classify the first experimental test failure without changing the scoped
# 48-kHz quality gate or repairing unrelated nondefault sample-rate behavior.
spec=importlib.util.spec_from_file_location('roundtrip_probe',root/'tests/test_auto_picture_roundtrip.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
output=evidence/'nondefault-8khz-control'
output.mkdir()
def encode_at_8khz(**kwargs):
    kwargs['config']=EncodeConfig(sample_rate_hz=8000)
    return encode_mfsk_wav(**kwargs)
with mock.patch.object(fixture,'tempfile',SimpleNamespace(TemporaryDirectory=lambda:nullcontext(str(output)))):
    with mock.patch.object(fixture,'encode_mfsk_wav',side_effect=encode_at_8khz):
        try:
            fixture.AutomaticPictureRoundtripTests('test_mixed_picture_modes_keep_order_files_and_resumed_text').test_mixed_picture_modes_keep_order_files_and_resumed_text()
        except AssertionError as error:
            failure=str(error)
        else:
            failure=None
products=decode_iq_products(meta_path=output/'broadcast.sigmf-meta',data_path=output/'broadcast.sigmf-data',
    artifact_dir=output/'candidate/artifacts',artifact_path_prefix='artifacts',include_diagnostic_manifest=True)
candidate=products.diagnostic_manifest
(output/'candidate/diagnostic.json').write_text(json.dumps(candidate,indent=2)+'\n')
old=baseline.run_reference_pipeline(meta_path=output/'broadcast.sigmf-meta',data_path=output/'broadcast.sigmf-data',
    start_sample=None,stop_sample=None,config=baseline.DecodeConfig(),artifact_dir=output/'baseline/artifacts',artifact_path_prefix='artifacts')
(output/'baseline/diagnostic.json').write_text(json.dumps(old,indent=2)+'\n')
artifacts={item['id']:item for item in candidate['artifacts']}
old_artifacts={item['id']:item for item in old['artifacts']}
quality=[]
same64=None
for index,picture in enumerate(candidate['pictures']):
    image=np.asarray(Image.open(output/'candidate'/artifacts[picture['raster_artifact']]['path']))
    truth=np.asarray(Image.open(output/f'source-{index}.png'))
    row={'mode':picture['mode'],'raw_mae_255':float(np.mean(np.abs(image.astype(float)-truth)))}
    if picture['mode']=='MFSK64':
        old_picture=next(item for item in old['pictures'] if item['mode']=='MFSK64')
        old_image=np.asarray(Image.open(output/'baseline'/old_artifacts[old_picture['raster_artifact']]['path']))
        same64=np.array_equal(image,old_image)
        row['baseline_pixel_identical']=same64
    quality.append(row)
record={'sample_rate_hz':8000,'fixture_assertion':failure,'pictures':quality,
        'interpretation':'Nondefault 8-kHz mixed fixture is outside the 48-kHz practical matrix; its MFSK64 quality defect also occurs in the retained baseline.'}
(evidence/'nondefault-8khz-control.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
assert same64
