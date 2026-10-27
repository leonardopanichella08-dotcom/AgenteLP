"""Rilevatore reale (Haar) su un volto vero (foto 'astronaut' di scikit-image) montato in un video 16:9."""
import subprocess

import numpy as np
import pytest

skimage_data = pytest.importorskip("skimage.data")
cv2 = pytest.importorskip("cv2")

from app.reframe import HaarDetector, build_path, crop_window, keyframes_for_segment, track_faces


@pytest.fixture(scope="module")
def face_video(tmp_path_factory):
    p = tmp_path_factory.mktemp("face") / "face.mp4"
    img = cv2.cvtColor(skimage_data.astronaut(), cv2.COLOR_RGB2BGR)       # 512x512
    img = cv2.resize(img, (640, 640))
    W, H = 1280, 720
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(p)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k in range(90):
        f = np.full((H, W, 3), 40, np.uint8)
        x0 = 600                       # il volto sta a destra del frame
        f[40:40 + 640, x0:x0 + 640] = img
        pr.stdin.write(f.tobytes())
    pr.stdin.close(); pr.wait()
    return p, 600 + (177 + 93 / 2) * 640 / 512     # centro x atteso del volto nel frame


def test_haar_finds_real_face_and_crop_follows_it(face_video):
    path, cx_expected = face_video
    tr = track_faces(str(path), [(0.0, 2.9)], HaarDetector())
    assert tr.coverage > 0.8 and len(tr.tracks) >= 1
    cw, ch = crop_window(1280, 720, 9 / 16)
    path_ = build_path(tr, {}, [], cw, ch)
    kf = keyframes_for_segment(path_, 0.5, 2.5, cw, ch, 1280, 720)
    cx_crop = np.mean([k["x"] + k["w"] / 2 for k in kf])
    assert abs(cx_crop - cx_expected) < 0.25 * cw, (cx_crop, cx_expected)
    assert cx_crop > 1280 / 2          # non resta al centro: segue il volto a destra
