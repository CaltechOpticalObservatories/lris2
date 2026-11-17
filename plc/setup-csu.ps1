<#
.SYNOPSIS
Install the CSU motion server into a TwinCAT project through the Automation Interface.

.DESCRIPTION
Opens the solution in a hidden TcXaeShell, replaces the PLC project's objects with
the sources in csu-motion-server, builds, links GVL_Axes.AxisRef[N] to NC Axis N,
and saves. With -Activate it also activates the configuration and starts the PLC
with its boot project. Close TcXaeShell before running; both would edit the same files.
#>
param(
    [Parameter(Mandatory)] [string] $Solution,
    [string] $PlcProject = "Untitled1",
    [int] $AxisCount = 23,
    [switch] $Activate
)
$ErrorActionPreference = "Stop"
$sources = Join-Path $PSScriptRoot "csu-motion-server"
$importOrder = "E_MoveMode", "ST_AxisCmd", "ST_AxisSts", "ST_Axis", "GVL_Axes", "FB_AxisServer", "MAIN"
$folderFor = @{ ".TcDUT" = "DUTs"; ".TcGVL" = "GVLs"; ".TcPOU" = "POUs" }
$existingItem = 58

# TcXaeShell rejects COM calls while busy; this filter retries them
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("00000016-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IOleMessageFilter {
  [PreserveSig] int HandleInComingCall(int dwCallType, IntPtr hTaskCaller, int dwTickCount, IntPtr lpInterfaceInfo);
  [PreserveSig] int RetryRejectedCall(IntPtr hTaskCallee, int dwTickCount, int dwRejectType);
  [PreserveSig] int MessagePending(IntPtr hTaskCallee, int dwTickCount, int dwPendingType);
}
public class MessageFilter : IOleMessageFilter {
  [DllImport("Ole32.dll")] static extern int CoRegisterMessageFilter(IOleMessageFilter newFilter, out IOleMessageFilter oldFilter);
  public static void Register() { IOleMessageFilter old; CoRegisterMessageFilter(new MessageFilter(), out old); }
  public static void Revoke() { IOleMessageFilter old; CoRegisterMessageFilter(null, out old); }
  int IOleMessageFilter.HandleInComingCall(int a, IntPtr b, int c, IntPtr d) { return 0; }
  int IOleMessageFilter.RetryRejectedCall(IntPtr a, int tick, int type) { return type == 2 && tick < 120000 ? 200 : -1; }
  int IOleMessageFilter.MessagePending(IntPtr a, int b, int c) { return 2; }
}
"@

function Import-Sources($sys, $base) {
    $pous = $sys.LookupTreeItem("$base^POUs")
    for ($i = $pous.ChildCount; $i -ge 1; $i--) { $pous.DeleteChild($pous.Child($i).Name) }
    foreach ($name in $importOrder) {
        $file = Get-ChildItem $sources -Filter "$name.*"
        $folder = $sys.LookupTreeItem("$base^" + $folderFor[$file.Extension])
        try { $folder.DeleteChild($name) } catch [System.Runtime.InteropServices.COMException] { }
        Write-Output ("imported " + $folder.CreateChild($name, $existingItem, $null, $file.FullName).PathName)
    }
}

function Assert-BuildClean($dte) {
    $dte.Solution.SolutionBuild.Build($true)
    $errors = @($dte.ToolWindows.ErrorList.ErrorItems | ForEach-Object { $_ } | Where-Object { $_.ErrorLevel -eq 2 })
    $errors | ForEach-Object { Write-Output ("  " + $_.FileName + ":" + $_.Line + " " + $_.Description) }
    if ($errors.Count -gt 0) { throw "build failed with $($errors.Count) errors; nothing linked or saved" }
    Write-Output "build clean"
}

function Connect-Axes($sys, $instance) {
    for ($n = 1; $n -le $AxisCount; $n++) {
        $axis = "TINC^NC-Task 1 SAF^Axes^Axis $n"
        $sys.LinkVariables("$instance^PlcTask Inputs^GVL_Axes.AxisRef[$n].NcToPlc", "$axis^Outputs^ToPlc")
        $sys.LinkVariables("$instance^PlcTask Outputs^GVL_Axes.AxisRef[$n].PlcToNc", "$axis^Inputs^FromPlc")
    }
    Write-Output "linked AxisRef[1..$AxisCount] to NC Axis 1..$AxisCount"
}

[MessageFilter]::Register()
$dte = $null
try {
    $dte = New-Object -ComObject "TcXaeShell.DTE.15.0"
    $dte.SuppressUI = $true
    $dte.Solution.Open((Resolve-Path $Solution).Path)
    $sys = $dte.Solution.Projects.Item(1).Object
    $base = "TIPC^$PlcProject^$PlcProject Project"

    Import-Sources $sys $base
    Assert-BuildClean $dte
    Connect-Axes $sys "TIPC^$PlcProject^$PlcProject Instance"
    $dte.ExecuteCommand("File.SaveAll")
    Write-Output "saved"

    if ($Activate) {
        $plc = $sys.LookupTreeItem("TIPC^$PlcProject")
        $plc.BootProjectAutostart = $true
        $plc.GenerateBootProject($true)
        $sys.ActivateConfiguration()
        $sys.StartRestartTwinCAT()
        Write-Output "activated and restarted TwinCAT"
    }
}
finally {
    if ($dte) { $dte.Quit() }
    [MessageFilter]::Revoke()
}
