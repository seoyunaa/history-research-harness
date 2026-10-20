[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$verifyScript = Join-Path $PSScriptRoot 'tools\verify.py'
$hierarchyScript = Join-Path $PSScriptRoot 'tools\check_harness_hierarchy.py'

if (-not (Test-Path -LiteralPath $verifyScript -PathType Leaf)) {
    Write-Error "검증기를 찾을 수 없습니다: $verifyScript"
    exit 2
}

function Invoke-HarnessVerify {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath,
        [string[]]$PrefixArguments = @()
    )

    Push-Location $PSScriptRoot
    try {
        & $PythonPath @PrefixArguments $verifyScript
        $verifyExitCode = $LASTEXITCODE

        # 하네스 구조 검사(필수 파일·참조 경로·데이터 누출)
        $hierarchyExitCode = 0
        if (Test-Path -LiteralPath $hierarchyScript -PathType Leaf) {
            & $PythonPath @PrefixArguments $hierarchyScript
            $hierarchyExitCode = $LASTEXITCODE
        }
    }
    finally {
        Pop-Location
    }

    if ($verifyExitCode -ne 0) {
        exit $verifyExitCode
    }
    exit $hierarchyExitCode
}

# 1. 일반 Python이 설치되어 있으면 우선 사용한다.
$pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($null -ne $pythonCommand) {
    Invoke-HarnessVerify -PythonPath $pythonCommand.Source
}

# 2. Windows Python 런처가 있으면 Python 3을 사용한다.
$pyCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($null -ne $pyCommand) {
    Invoke-HarnessVerify -PythonPath $pyCommand.Source -PrefixArguments @('-3')
}

Write-Error @"
Python 3 실행 파일을 찾지 못했습니다.
Python 3.10 이상을 설치한 뒤 다시 실행하거나, environment.yml을 참고해 환경을 만드세요.
"@
exit 127
