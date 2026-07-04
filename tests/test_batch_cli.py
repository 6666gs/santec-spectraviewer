import csv
import numpy as np


def _write_two_col(path, lam, t_db):
    with open(path, 'w') as f:
        for x, y in zip(lam, t_db):
            f.write(f"{x:.4f},{y:.4f}\n")


def test_cli_end_to_end(tmp_path):
    from batch_ring_q import main
    lam = np.arange(1500, 1600, 0.002)
    t_lin = np.ones_like(lam)
    for c0 in np.arange(1504, 1596, 9.0):
        t_lin *= (1 - 0.7 / (1 + ((lam - c0) / 0.03) ** 2))
    t_db = 10 * np.log10(np.clip(t_lin, 1e-9, None))
    d = tmp_path / "data"
    d.mkdir()
    _write_two_col(d / "ringA_loss.csv", lam, t_db)

    out = tmp_path / "out"
    rc = main([str(d), "--out", str(out), "--min-r2", "0.8"])
    assert rc == 0
    assert (out / "ringA_loss_Qdist.png").exists()

    csv_path = out / "ringA_loss_results.csv"
    assert csv_path.exists()
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1
    expected_cols = {'mode_id', 'fsr_nm', 'lambda0_nm', 'ql', 'qi',
                     'er_db', 'gamma_pm', 'r_squared'}
    assert expected_cols <= set(rows[0].keys())


def test_cli_no_files(tmp_path):
    from batch_ring_q import main
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = main([str(empty), "--out", str(tmp_path / "o")])
    assert rc == 1
