<#
    GDID F!K - Windows Global Device ID (GDID) Reader
    ---------------------------------------------------
    Liest die persistente "Global Device ID" (GDID) aus, die Microsoft
    intern zur eindeutigen Identifikation einer Windows-Installation
    verwendet (Device PUID, ueber wlidsvc / login.live.com vergeben).

    Bekannte Fundstellen (Stand Juli 2026, oeffentlich dokumentiert
    u.a. im FBI-Verfahren gegen "Scattered Spider" und von Microsoft
    bestaetigt):

      HKCU\SOFTWARE\Microsoft\IdentityCRL\ExtendedProperties  -> LID
      HKLM\SOFTWARE\Microsoft\IdentityStore                   -> DeviceId, LID
      HKLM\SOFTWARE\Microsoft\IdentityCRL\NegativeCache        -> Token-Scopes (Zusatzinfo)

    Das Format ist ein kleines "g" gefolgt von einer Dezimalzahl,
    z.B. g1234567890123456 (64-bit Passport Unique ID).
#>

[CmdletBinding()]
param(
    [switch]$Raw   # gibt zusaetzlich alle Rohwerte aus jedem Fundort aus
)

function Write-Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Get-RegValueSafe($path, $name) {
    try {
        if (Test-Path $path) {
            $item = Get-ItemProperty -Path $path -Name $name -ErrorAction Stop
            return $item.$name
        }
    } catch {
        return $null
    }
    return $null
}

function Find-GdidLikeValues($path) {
    $results = @()
    if (-not (Test-Path $path)) { return $results }
    try {
        $props = Get-ItemProperty -Path $path -ErrorAction Stop
        foreach ($prop in $props.PSObject.Properties) {
            if ($prop.Name -match '^(LID|DeviceId|GlobalDeviceId|DevicePUID)$' -or
                ($prop.Value -is [string] -and $prop.Value -match '^g\d{10,25}$')) {
                $results += [PSCustomObject]@{
                    Path  = $path
                    Name  = $prop.Name
                    Value = $prop.Value
                }
            }
        }
    } catch {}
    return $results
}

Write-Host "GDID F!K - Windows Global Device ID Reader" -ForegroundColor Yellow
Write-Host "Quelle: HKCU/HKLM Identity-Registrierungspfade`n"

$locations = @(
    "HKCU:\SOFTWARE\Microsoft\IdentityCRL\ExtendedProperties",
    "HKLM:\SOFTWARE\Microsoft\IdentityStore",
    "HKLM:\SOFTWARE\Microsoft\IdentityCRL\NegativeCache"
)

$allFindings = @()
foreach ($loc in $locations) {
    Write-Section $loc
    if (-not (Test-Path $loc)) {
        Write-Host "  (nicht vorhanden auf diesem System)" -ForegroundColor DarkGray
        continue
    }

    $findings = Find-GdidLikeValues $loc
    if ($findings.Count -eq 0) {
        Write-Host "  Keine GDID/LID/DeviceId-Werte direkt in diesem Schluessel gefunden." -ForegroundColor DarkGray
    } else {
        foreach ($f in $findings) {
            Write-Host ("  {0,-16} = {1}" -f $f.Name, $f.Value) -ForegroundColor Green
            $allFindings += $f
        }
    }

    # Unterschluessel (z.B. ExtendedProperties hat oft Subkeys pro Konto)
    try {
        $subkeys = Get-ChildItem -Path $loc -ErrorAction Stop
        foreach ($sk in $subkeys) {
            $skPath = $sk.PSPath
            $subFindings = Find-GdidLikeValues $skPath
            foreach ($f in $subFindings) {
                Write-Host ("  [{0}] {1,-16} = {2}" -f $sk.PSChildName, $f.Name, $f.Value) -ForegroundColor Green
                $allFindings += $f
            }
            if ($Raw) {
                try {
                    $allProps = Get-ItemProperty -Path $skPath -ErrorAction Stop
                    foreach ($p in $allProps.PSObject.Properties) {
                        if ($p.Name -notmatch '^PS') {
                            Write-Host ("    (raw) [{0}] {1} = {2}" -f $sk.PSChildName, $p.Name, $p.Value) -ForegroundColor DarkGray
                        }
                    }
                } catch {}
            }
        }
    } catch {}
}

Write-Section "Zusammenfassung"
$gdidCandidates = @($allFindings | Where-Object { $_.Value -match '^g\d{10,25}$' })

# LID wird typischerweise als 16-stelliger Hex-Wert gespeichert (little-endian
# QWORD). Die oeffentlich sichtbare GDID ("g<Dezimalzahl>") ist die Dezimal-
# darstellung dieses Werts mit vorangestelltem "g".
$lidCandidates = @($allFindings | Where-Object { $_.Name -eq 'LID' -and $_.Value -match '^[0-9A-Fa-f]{16}$' })

if ($gdidCandidates.Count -gt 0) {
    $unique = $gdidCandidates | Select-Object -ExpandProperty Value -Unique
    foreach ($g in $unique) {
        Write-Host "GDID gefunden: $g" -ForegroundColor Yellow
    }
} elseif ($lidCandidates.Count -gt 0) {
    $uniqueLids = $lidCandidates | ForEach-Object { $_.Value } | Select-Object -Unique
    foreach ($lidValue in $uniqueLids) {
        try {
            $dec = [Convert]::ToUInt64($lidValue, 16)
            Write-Host "LID (Hex):      $lidValue" -ForegroundColor DarkGray
            Write-Host "GDID (Dezimal): g$dec" -ForegroundColor Yellow
        } catch {
            Write-Host "LID gefunden, konnte aber nicht konvertiert werden: $lidValue" -ForegroundColor Red
        }
    }
} else {
    Write-Host "Keine GDID/LID gefunden." -ForegroundColor Red
    Write-Host "Moegliche Gruende: Geraet ist nicht mit einem Microsoft-Konto verknuepft," -ForegroundColor DarkGray
    Write-Host "oder die GDID liegt (je nach Windows-Version/Build) an einem anderen Ort." -ForegroundColor DarkGray
    if ($allFindings.Count -gt 0) {
        Write-Host "`nGefundene verwandte Werte:" -ForegroundColor DarkGray
        $allFindings | Format-Table Path, Name, Value -AutoSize
    }
}

Write-Host ""
Write-Host "Tipp: mit -Raw alle Rohwerte je Registry-Pfad anzeigen." -ForegroundColor DarkGray
