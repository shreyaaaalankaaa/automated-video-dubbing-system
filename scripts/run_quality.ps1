param(
    [Parameter(Mandatory=$true)][string]$Url,
    [string]$Model = "small",
    [string]$Voice = "en-US-AriaNeural"
)

$ErrorActionPreference = "Stop"
& .\.venv\Scripts\Activate.ps1
python main.py $Url --mode quality --model $Model --voice $Voice --output outputs
