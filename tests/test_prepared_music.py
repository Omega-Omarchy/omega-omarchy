import hashlib
import json
from pathlib import Path

import pytest
from omega_omarchy import audio_build


def _cue(path):
    return {'id':'chapter-one', 'loop':True, 'prepared':{'sixteen-bit':{
        'file':path.name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'loop':True}}}


def test_prepared_music_rejects_changed_content_path_escape_and_loop_mismatch(tmp_path):
    path = tmp_path/'reviewed.ogg'; path.write_bytes(b'OggSprepared-test')
    cue = _cue(path)
    assert audio_build._prepared_music_files(cue,tmp_path) == {'sixteen-bit':path}
    path.write_bytes(b'OggSchanged')
    with pytest.raises(RuntimeError,match='checksum'):
        audio_build._prepared_music_files(cue,tmp_path)
    cue = _cue(path); cue['prepared']['sixteen-bit']['file'] = '../reviewed.ogg'
    with pytest.raises(RuntimeError,match='path'):
        audio_build._prepared_music_files(cue,tmp_path)
    cue = _cue(path); cue['prepared']['sixteen-bit']['loop'] = False
    with pytest.raises(RuntimeError,match='loop'):
        audio_build._prepared_music_files(cue,tmp_path)


def test_builder_copies_reviewed_tier_without_resynthesis_and_records_provenance(tmp_path,monkeypatch):
    source = tmp_path/'source/audio'; source.mkdir(parents=True)
    master = source/'master.wav'; master.write_bytes(b'master')
    prepared = source/'reviewed.ogg'; prepared.write_bytes(b'OggSprepared-test')
    digest = hashlib.sha256(prepared.read_bytes()).hexdigest()
    (source/'audio-manifest.toml').write_text(f'''schema_version = 1
sfx = []
[master]
file = "master.wav"
provenance = "test"
rights = "synthetic"
[scene_music]
action = "chapter-one"
[[music]]
id = "chapter-one"
bus = "music"
caption = "Chapter"
gain = 1.0
start = 0.0
end = 8.0
loop = true
crossfade = 0.2
[music.prepared.sixteen-bit]
file = "reviewed.ogg"
sha256 = "{digest}"
loop = true
''')
    calls = []
    def render(ffmpeg,master,target,tier,**kwargs):
        calls.append(tier); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'OggSfallback')
    monkeypatch.setattr(audio_build,'_render_music',render)
    monkeypatch.setattr(audio_build,'_emit_sfx_masters',lambda root:None)
    monkeypatch.setattr(audio_build,'_probe_duration',lambda *args:8.0)
    monkeypatch.setattr(audio_build,'_probe_levels',lambda *args:{'peak_db':-1.0})
    monkeypatch.setattr(audio_build.shutil,'which',lambda program:program)
    path = audio_build.build_audio_assets(tmp_path)
    result = json.loads(path.read_text())['cues']['chapter-one']
    assert calls == ['high','ultra']
    assert (tmp_path/'audio'/result['files']['sixteen-bit']).read_bytes() == prepared.read_bytes()
    assert result['sourceDigests']['sixteen-bit'] == f'sha256:{digest}'
    assert result['renderMethods']['sixteen-bit'] == 'prepared-authoring-render'
    audio_build.build_audio_assets(tmp_path)
    assert calls == ['high','ultra']
