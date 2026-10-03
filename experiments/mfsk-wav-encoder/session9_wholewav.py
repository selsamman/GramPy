"""Collect seven settled picture buffers from unchanged whole-WAV Pi replays."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
import shutil, subprocess, sys, tarfile
from PIL import Image
from session9_probe import metrics

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    bundle,source,paired,output = map(Path,sys.argv[1:5])
    output.mkdir()
    binary = Path("/opt/radiogram/reference/session10d/builds/fldigi-4.2.13-pi3-aarch64/install/bin/fldigi")
    assert sha(binary)=="dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3"
    text = (paired/"receiver-adapter-snapshot.sh").read_text()
    assert text.count("python_status=0\n")==1
    text = text.replace("python_status=0\n",f'''"{sys.executable}" "{bundle}/session9_widget.py" "{binary}" "$config_dir" "$work_dir" >"$work_dir/viewer-capture.log" 2>&1 &
viewer_capture_pid=$!
python_status=0
''')
    anchor = """python3 - "$config_dir" "$work_dir" <<'SNAPSHOT'"""
    assert text.count(anchor)==1
    text = text.replace(anchor,'''touch "$work_dir/viewer-capture.done"
wait "$viewer_capture_pid"
'''+anchor)
    adapter = output/"receiver-adapter-display.sh"
    adapter.write_text(text)
    adapter.chmod(0o755)
    for filename in ("session9_wholewav.py","session9_widget.py"): shutil.copy(bundle/filename,output)
    rgb = Image.open(source/"inputs/primary-color-8x4.png").convert("RGB").tobytes()
    gray = bytes((31*r+61*g+8*b)//100 for r,g,b in zip(rgb[::3],rgb[1::3],rgb[2::3]))
    gray_rgb = bytes(v for v in gray for _ in range(3))
    shutil.copy(source/"inputs/primary-color-8x4.png",output)
    layout = [
        ("rsid-mixed-audio-silence-picture","ccba1c03648cb7a3f3edc96b323eed713a347c7b175435d61eab1d137012eb41","color",[8]),
        ("mfsk32-grayscale-speeds","1811efb18420e6d49881db30eeb4204c0d3afe6a8a03f62b91b29a5d7498f73e","grayscale",[8,4,2]),
        ("mfsk64-color-speeds","0204283ff510b146eea6a7fc6795a7a1429f537c60b7ed6ce5a65a9d54ad80ea","color",[8,4,2])]
    results = []
    for name,expected_hash,color,speeds in layout:
        original,case = source/"cases"/name,output/name
        case.mkdir()
        wav = original/"generated.wav"
        assert sha(wav)==expected_hash
        config = case/"config"
        config.mkdir()
        with tarfile.open(original/"decode.tar") as archive:
            member = archive.extractfile("./fldigi/config-start/fldigi_def.xml")
            assert member is not None
            (config/"fldigi_def.xml").write_bytes(member.read())
        for filename in ("composition.json","encoder-result.json"): shutil.copy(original/filename,case)
        work = case/"work"
        command = [str(adapter),"--input",str(wav),"--output",str(case/"decode.tar"),
                   "--work-dir",str(work),"--config-dir",str(config),"--mode","BPSK31","--rxid","on","--afc","off",
                   "--audio-frequency-hz","1500","--status-interval-sec","0.25","--post-playback-sec","15",
                   "--debug-bundle","full","--nice","0","--audio-backend","alsa-loopback","--alsa-capture-plugin","plug"]
        (case/"command.json").write_text(json.dumps(command,indent=2)+"\n")
        env = dict(os.environ,PATH=str(binary.parent)+":"+os.environ["PATH"])
        print("START",name,flush=True)
        with (case/"adapter.stdout").open("w") as stdout,(case/"adapter.stderr").open("w") as stderr:
            run = subprocess.run(command,env=env,stdout=stdout,stderr=stderr,timeout=240)
        if run.returncode: raise RuntimeError(f"adapter failed: {name}: {run.returncode}")
        captures = json.loads((work/"viewer-captures/captures.json").read_text())
        assert len(captures)==len(speeds),(name,captures)
        final_pixels = Image.open(work/"viewer-captures"/captures[-1]["path"]).convert("RGB").tobytes()
        assert final_pixels==(work/"viewer.rgb").read_bytes(),"live read disagrees with post-playback widget dump"
        for capture,speed in zip(captures,speeds):
            actual = Image.open(work/"viewer-captures"/capture["path"]).convert("RGB").tobytes()
            results.append({"case":name,"color":color,"speed":speed,"wav_sha256":expected_hash,
                            "live_read_final_matches_gdb":True,"capture":capture,
                            "viewer":metrics(actual,rgb if color=="color" else gray_rgb)})
        (output/"results.json").write_text(json.dumps(results,indent=2)+"\n")
        print("END",name,"captured",len(captures),"settled pictures; final buffer verified",flush=True)
    (output/"identity.json").write_text(json.dumps({"receiver_sha256":sha(binary),"adapter_sha256":sha(adapter),
        "artifact_method":"stable read-only widget bytes; no pause during playback; final pixels verified against gdb",
        "whole_wav":True,"rxid":True,"initial_mode":"BPSK31","manual_mode_changes":0},indent=2)+"\n")

if __name__=="__main__": main()
