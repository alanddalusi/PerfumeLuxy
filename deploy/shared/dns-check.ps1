# Read-only DNS check for perfumeriaelbuenolor.es (run on Windows PowerShell 5.1+).
#   .\deploy\shared\dns-check.ps1 -Expect OVH   # before the change: still on redirect.ovh.net
#   .\deploy\shared\dns-check.ps1 -Expect VPS   # after the change: @ and www on the VPS
# Mail records (MX, SPF) and NS must be identical in both cases. Nothing is modified.
param([ValidateSet('OVH', 'VPS')][string]$Expect = 'VPS')

$Domain = 'perfumeriaelbuenolor.es'
$Vps = '146.59.35.127'
$Ovh = '213.186.33.5'
$Want = if ($Expect -eq 'VPS') { $Vps } else { $Ovh }
$MailMx = @('1 mx1.mail.ovh.net', '5 mx2.mail.ovh.net', '100 mx3.mail.ovh.net')
$Spf = 'v=spf1 include:mx.ovh.com -all'
$Ns = @('dns103.ovh.net', 'ns103.ovh.net')
$Servers = @('dns103.ovh.net', '1.1.1.1', '8.8.8.8')
$script:fails = 0

function Report($ok, $text) { if ($ok) { "PASS  $text" } else { $script:fails++; "FAIL  $text" } }
function Ask($name, $type, $server) {
    try { Resolve-DnsName $name -Type $type -Server $server -DnsOnly -ErrorAction Stop | Where-Object { $_.Section -eq 'Answer' -and $_.Type -eq $type } }
    catch { @() }
}

foreach ($s in $Servers) {
    foreach ($n in @($Domain, "www.$Domain")) {
        $a = @(Ask $n 'A' $s | ForEach-Object IPAddress | Sort-Object -Unique)
        Report (($a.Count -eq 1) -and ($a[0] -eq $Want)) ("{0,-28} A    @{1,-15} -> {2} (expected {3})" -f $n, $s, ($a -join ','), $Want)
    }
    $aaaa = @(Ask $Domain 'AAAA' $s)
    Report ($aaaa.Count -eq 0) ("{0,-28} AAAA @{1,-15} -> none expected for now" -f $Domain, $s)
    $mx = @(Ask $Domain 'MX' $s | ForEach-Object { "$($_.Preference) $($_.NameExchange)" } | Sort-Object)
    Report ((Compare-Object $mx ($MailMx | Sort-Object)) -eq $null) ("{0,-28} MX   @{1,-15} -> {2}" -f $Domain, $s, ($mx -join '; '))
    $txt = @(Ask $Domain 'TXT' $s | ForEach-Object { $_.Strings -join '' })
    Report ($txt -contains $Spf) ("{0,-28} SPF  @{1,-15} -> unchanged" -f $Domain, $s)
    if ($Expect -eq 'VPS') {
        Report (-not ($txt | Where-Object { $_ -match '^\d\|' })) ("{0,-28} TXT  @{1,-15} -> OVH redirect record removed" -f $Domain, $s)
    }
}
$ns = @(Ask $Domain 'NS' 'dns103.ovh.net' | ForEach-Object NameHost | Sort-Object)
Report ((Compare-Object $ns $Ns) -eq $null) ("NS unchanged: {0}" -f ($ns -join ', '))
"----"
"fails=$script:fails (public resolvers may lag behind dns103 for up to the record TTL)"
exit [int]($script:fails -gt 0)
