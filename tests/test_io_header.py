import numpy as np

from core.io import detect_header_rows, load_spectrum

SANTEC = """Instrument,MPM
Start,1500
Stop,1600
Step,0.001
Source power,0
line5,x
line6,x
line7,x
line8,x
line9,x
line10,x
line11,x
line12,x
Wavelength,IL[CH1]
1500.000,-20.10
1500.001,-20.20
1500.002,-20.30
1500.003,-20.40
"""

TWO_COL = "1500.000,-20.10\n1500.001,-20.20\n1500.002,-20.30\n1500.003,-20.40\n"


def test_detect_header_santec(tmp_path):
    p = tmp_path / "a_loss.csv"
    p.write_text(SANTEC)
    assert detect_header_rows(str(p)) == 13  # 列头行(Wavelength,IL[CH1]) 的索引


def test_detect_header_two_col(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text(TWO_COL)
    assert detect_header_rows(str(p)) == 0


def test_load_spectrum_two_col(tmp_path):
    p = tmp_path / "b.csv"
    p.write_text(TWO_COL)
    lam, loss, meta = load_spectrum(str(p))
    assert lam.shape == loss.shape and lam.size == 4
    assert np.isclose(lam[0], 1500.0) and np.isclose(loss[0], -20.10)
