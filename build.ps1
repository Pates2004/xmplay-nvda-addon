[CmdletBinding()]
param(
	[string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $projectRoot
$addonRoot = Join-Path $projectRoot 'addon'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
	$packagePath = Join-Path $workspaceRoot 'xmplayAccessibility-1.1.0.nvda-addon'
} else {
	$packagePath = $OutputPath
}

$env:PYTHONDONTWRITEBYTECODE = '1'
python (Join-Path $projectRoot 'tools\check_syntax.py')
if ($LASTEXITCODE -ne 0) { throw "Syntax validation failed with exit code $LASTEXITCODE" }
$potPath = Join-Path $projectRoot 'xmplayAccessibility.pot'
Push-Location $projectRoot
try {
	xgettext --language=Python --keyword=_ --from-code=UTF-8 --package-name=xmplayAccessibility --package-version=1.1.0 -o 'xmplayAccessibility.pot' 'addon\appModules\xmplay\__init__.py' 'addon\appModules\xmplay\dialogs.py' 'addon\globalPlugins\xmplayAccessibility\settingsPanel.py'
	if ($LASTEXITCODE -ne 0) { throw "Message extraction failed with exit code $LASTEXITCODE" }
} finally {
	Pop-Location
}
python (Join-Path $projectRoot 'tools\build_locale.py')
if ($LASTEXITCODE -ne 0) { throw "Locale generation failed with exit code $LASTEXITCODE" }
$moPath = Join-Path $addonRoot 'locale\pl\LC_MESSAGES\nvda.mo'
$poPath = Join-Path $addonRoot 'locale\pl\LC_MESSAGES\nvda.po'
msgfmt --check-format --check-header -o $moPath $poPath
if ($LASTEXITCODE -ne 0) { throw "Message catalog compilation failed with exit code $LASTEXITCODE" }
python -m unittest discover -s (Join-Path $projectRoot 'tests') -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed with exit code $LASTEXITCODE" }

$resolvedWorkspace = [IO.Path]::GetFullPath($workspaceRoot)
$resolvedPackage = [IO.Path]::GetFullPath($packagePath)
if (-not $resolvedPackage.StartsWith($resolvedWorkspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
	throw "Refusing to write outside the workspace: $resolvedPackage"
}
if (Test-Path -LiteralPath $resolvedPackage) {
	Remove-Item -LiteralPath $resolvedPackage -Force
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($addonRoot, $resolvedPackage, [IO.Compression.CompressionLevel]::Optimal, $false)
Write-Output "Built $resolvedPackage"
