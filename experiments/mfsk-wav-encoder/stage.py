"""Stage a locally built wheel and print a Pi-wrapper command file.

Run via tools/mac-local.sh. Machine-specific transport remains in .local/.
"""
import base64, hashlib, io, json, pathlib, shutil, subprocess, tarfile
root=pathlib.Path.cwd()
bundle=root/'.local/session8/bundle'
bundle.mkdir(exist_ok=True)
shutil.copytree(root/'.local/session8/distribution',bundle/'distribution',dirs_exist_ok=True)
for src,name in [('experiments/mfsk-wav-encoder/qualification.py','qualification.py'),('tools/pi-qualify-mfsk-encoder.sh','pi-qualify-mfsk-encoder.sh'),('docs/encoder/data/mfsk_encoder_pi_matrix_v2.json','matrix.json'),('docs/encoder/data/mfsk_encoder_pi_matrix_v1.json','matrix-v1.json'),('docs/encoder/data/mfsk_encoder_rsid_oracle_v1.json','rsid-oracle.json'),('docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v2.schema.json','manifest-schema.json'),('tests/fixtures/mfsk/primary-color-8x4.png','primary-color-8x4.png')]:
 shutil.copy(root/src,bundle/name)
(bundle/'revision.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD'],text=True))
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src/grampy').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='.DS_Store'}
(bundle/'candidate-source-hashes.json').write_text(json.dumps(files,indent=2)+'\n')
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as tar: tar.add(bundle,arcname='bundle')
encoded=base64.b64encode(buf.getvalue()).decode()
command='''#!/bin/sh
set -eu
stage=$(mktemp -d /var/tmp/grampy-encoder-session8.XXXXXX)
base64 -d > "$stage/bundle.tar.gz" <<'BUNDLE'
'''+encoded+'''
BUNDLE
tar -xzf "$stage/bundle.tar.gz" -C "$stage"
printf 'qualification_root=%s\n' "$stage"
sh "$stage/bundle/pi-qualify-mfsk-encoder.sh" "$stage/bundle" "$stage/evidence"
printf 'EVIDENCE_BASE64_BEGIN\n'
tar --exclude=venv --exclude=work --exclude=config -czf - -C "$stage/evidence" . | base64
printf 'EVIDENCE_BASE64_END\n'
'''
(root/'.local/pi-session8-run.sh').write_text(command)
print('Staged', len(buf.getvalue()),'bytes; source revision retained')
