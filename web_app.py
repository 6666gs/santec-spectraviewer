#!/usr/bin/env python3
"""SpectraViewer Web 版入口 (Dash)。

用法:
    python web_app.py             # 本地启动，浏览器访问 http://localhost:8050
    python web_app.py --port 8050 # 指定端口
"""

import sys
import argparse

from web import app as dash_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SpectraViewer Web')
    parser.add_argument('--port', type=int, default=8050)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    print(f"SpectraViewer Web 启动中...")
    print(f"请在浏览器访问: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")

    dash_app.server.run(host=args.host, port=args.port, debug=args.debug)
