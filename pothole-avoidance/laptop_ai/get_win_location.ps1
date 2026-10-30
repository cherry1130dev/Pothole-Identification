Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(4000) | Out-Null
    $netTask.Result
}

try {
    [Windows.Devices.Geolocation.Geolocator, Windows.Devices.Geolocation, ContentType=WindowsRuntime] | Out-Null
    $access = Await ([Windows.Devices.Geolocation.Geolocator]::RequestAccessAsync()) ([Windows.Devices.Geolocation.GeolocationAccessStatus])
    
    if ($access -eq 'Allowed') {
        $locator = [Windows.Devices.Geolocation.Geolocator]::new()
        $pos = Await ($locator.GetGeopositionAsync()) ([Windows.Devices.Geolocation.Geoposition])
        $coord = $pos.Coordinate
        $point = $coord.Point.Position
        
        [PSCustomObject]@{
            Success = $true
            Latitude = [math]::Round($point.Latitude, 6)
            Longitude = [math]::Round($point.Longitude, 6)
            AccuracyMeters = [math]::Round($coord.Accuracy, 1)
            Altitude = [math]::Round($point.Altitude, 1)
        } | ConvertTo-Json -Compress
    } else {
        [PSCustomObject]@{
            Success = $false
            Error = "Access denied: $access"
        } | ConvertTo-Json -Compress
    }
} catch {
    [PSCustomObject]@{
        Success = $false
        Error = $_.Exception.Message
    } | ConvertTo-Json -Compress
}
