@echo off
chcp 65001 >nul
echo 正在安装依赖...
pip install -r requirements.txt -q
echo.
echo 启动OA系统...
echo 请在浏览器打开: http://localhost:5000
echo 默认管理员账号: admin  密码: admin123
echo 按 Ctrl+C 可停止服务
echo.
python app.py
pause
