@echo off
chcp 65001 >nul

echo ========================================
echo  GitHub Setup Script (Windows)
echo ========================================
echo.

:: Check GitHub CLI
where gh >nul 2>&1
if errorlevel 1 (
    echo [信息] GitHub CLI 未安裝
    echo 請訪問 https://cli.github.com/ 下載安裝
    pause
    exit /b 1
)

echo [信息] GitHub CLI 已安裝
echo.

:: Get GitHub Token
set /p GITHUB_TOKEN="請輸入你的 GitHub Token: "

if "%GITHUB_TOKEN%"=="" (
    echo [錯誤] Token 不能为空
    pause
    exit /b 1
)

:: Login with token
echo [信息] 正在配置 GitHub CLI...
echo %GITHUB_TOKEN% | gh auth login --with-token

:: Check status
gh auth status
if errorlevel 1 (
    echo [錯誤] GitHub CLI 配置失敗
    pause
    exit /b 1
)

echo.
echo ========================================
echo  GitHub Setup Complete!
echo ========================================
echo.
echo 接下來：
echo 1. cd scripts
echo 2. git init ^&^& git add . ^&^& git commit -m "Initial commit"
echo 3. git remote add origin https://github.com/USERNAME/REPO.git
echo 4. git push -u origin main
echo.
echo GitHub Actions 會自動觸發並生成 .exe 文件
echo.
pause