[CmdletBinding()]
param(
	[string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$addonRoot = Join-Path $projectRoot 'addon'
$manifestText = [IO.File]::ReadAllText((Join-Path $addonRoot 'manifest.ini'))
$versionMatch = [regex]::Match($manifestText, '(?m)^version\s*=\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$')
if (-not $versionMatch.Success) { throw 'Missing add-on version in manifest.ini' }
$addonVersion = $versionMatch.Groups[1].Value
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
	$packagePath = Join-Path $projectRoot "Installfiles\xmplayAccessibility-$addonVersion.nvda-addon"
} else {
	$packagePath = $OutputPath
}
$resolvedPackage = [IO.Path]::GetFullPath($packagePath)
if (-not $resolvedPackage.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
	throw "Refusing to write outside the project: $resolvedPackage"
}
if (Test-Path -LiteralPath $resolvedPackage) {
	throw "Package already exists; move the previous build before rebuilding: $resolvedPackage"
}

$env:PYTHONDONTWRITEBYTECODE = '1'
python (Join-Path $projectRoot 'tools\check_syntax.py')
if ($LASTEXITCODE -ne 0) { throw "Syntax validation failed with exit code $LASTEXITCODE" }
$potPath = Join-Path $projectRoot 'xmplayAccessibility.pot'
Push-Location $projectRoot
try {
	xgettext --language=Python --keyword=_ --keyword=N_ --from-code=UTF-8 --package-name=xmplayAccessibility --package-version=$addonVersion -o 'xmplayAccessibility.pot' 'addon\appModules\xmplay\__init__.py' 'addon\appModules\xmplay\backend.py' 'addon\appModules\xmplay\dialogs.py' 'addon\globalPlugins\xmplayAccessibility\__init__.py' 'addon\globalPlugins\xmplayAccessibility\settingsPanel.py'
	if ($LASTEXITCODE -ne 0) { throw "Message extraction failed with exit code $LASTEXITCODE" }
	$potContent = [IO.File]::ReadAllText($potPath)
	$potContent = [Text.RegularExpressions.Regex]::Replace(
		$potContent,
		'"POT-Creation-Date: [^"\r\n]*\\n"',
		'"POT-Creation-Date: 2026-10-20 00:00+0200\n"'
	)
	[IO.File]::WriteAllText($potPath, $potContent, [Text.UTF8Encoding]::new($false))
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

$packageDirectory = Split-Path -Parent $resolvedPackage
if (-not (Test-Path -LiteralPath $packageDirectory)) { New-Item -ItemType Directory -Path $packageDirectory | Out-Null }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($addonRoot, $resolvedPackage, [IO.Compression.CompressionLevel]::Optimal, $false)
python (Join-Path $projectRoot 'tools\validate_addon.py') $resolvedPackage
if ($LASTEXITCODE -ne 0) { throw "Package validation failed with exit code $LASTEXITCODE" }
Write-Output "Built $resolvedPackage"
