(*
    CSU motion server, TwinCAT 3 Structured Text.

    Python reads and writes GVL_Axes.Axis over ADS (coo-ethercat's TwinCAT
    backend); all drive supervision stays on the PLC. AxisRef[i] is linked to
    NC axis i, which drives CSU-(i-1). Requires library Tc2_MC2.

    This is the source: plc/gen_tc.py splits it into plc/csu-motion-server/.
*)

// ===================== DUT: E_MoveMode (enum) =====================
TYPE E_MoveMode :
(
    eAbsolute := 0,
    eRelative := 1,
    eVelocity := 2
) DINT;
END_TYPE

// ===================== DUT: ST_AxisCmd =====================
TYPE ST_AxisCmd :
STRUCT
    bEnable        : BOOL;      // level: hold TRUE to keep the drive enabled
    bExecute       : BOOL;      // edge: starts the move described below
    bStop          : BOOL;      // edge
    bReset         : BOOL;      // edge: clears a latched fault
    bHome          : BOOL;      // edge
    eMode          : E_MoveMode;
    fTarget        : LREAL;     // absolute position, or distance if eRelative
    fVelocity      : LREAL;
    fAcceleration  : LREAL;
    fDeceleration  : LREAL;
END_STRUCT
END_TYPE

// ===================== DUT: ST_AxisSts =====================
TYPE ST_AxisSts :
STRUCT
    bReady    : BOOL;
    bEnabled  : BOOL;
    bMoving   : BOOL;
    bError    : BOOL;
    nErrorId  : UDINT;
    eState    : DINT;      // PLCopen state, see AxisState in interface.py
    fPosition : LREAL;
    fVelocity : LREAL;
    nSeq      : UDINT;     // ++ on each completed command; the client's
                           // completion handshake, robust to missed polls
END_STRUCT
END_TYPE

// ===================== DUT: ST_Axis =====================
TYPE ST_Axis :
STRUCT
    Cmd : ST_AxisCmd;
    Sts : ST_AxisSts;
END_STRUCT
END_TYPE

// ===================== GVL: GVL_Axes =====================
VAR_GLOBAL
    // MAIN only serves 1..nAxisCount; raise the array bounds if more drives are added
    nAxisCount : INT := 23;
    Axis       : ARRAY [1..24] OF ST_Axis;
    AxisRef    : ARRAY [1..24] OF AXIS_REF;   // AxisRef[1] -> NC Axis 1 -> CSU-0
END_VAR

// ===================== POU: FB_AxisServer (FUNCTION_BLOCK) =====================
FUNCTION_BLOCK FB_AxisServer
VAR_IN_OUT
    stAxis : ST_Axis;
    Ref    : AXIS_REF;
END_VAR
VAR
    fbPower     : MC_Power;
    fbMoveAbs   : MC_MoveAbsolute;
    fbMoveRel   : MC_MoveRelative;
    fbStop      : MC_Stop;
    fbReset     : MC_Reset;
    fbHome      : MC_Home;
    fbStatus    : MC_ReadStatus;

    rExecute    : R_TRIG;
    rStop       : R_TRIG;
    rReset      : R_TRIG;
    rHome       : R_TRIG;

    bBusy       : BOOL;
    eActive     : E_MoveMode;
END_VAR

// --- status refresh (every cycle) ---
fbStatus(Axis := Ref, Enable := TRUE);

stAxis.Sts.fPosition := Ref.NcToPlc.ActPos;
stAxis.Sts.fVelocity := Ref.NcToPlc.ActVelo;
stAxis.Sts.bEnabled  := fbPower.Status;
stAxis.Sts.bMoving   := fbStatus.DiscreteMotion OR fbStatus.ContinuousMotion
                        OR fbStatus.Homing OR fbStatus.Stopping;
stAxis.Sts.bReady    := fbStatus.StandStill OR fbStatus.Disabled;

IF fbStatus.Disabled THEN        stAxis.Sts.eState := 0;
ELSIF fbStatus.StandStill THEN   stAxis.Sts.eState := 1;
ELSIF fbStatus.Homing THEN       stAxis.Sts.eState := 2;
ELSIF fbStatus.DiscreteMotion THEN stAxis.Sts.eState := 3;
ELSIF fbStatus.ContinuousMotion THEN stAxis.Sts.eState := 4;
ELSIF fbStatus.Stopping THEN     stAxis.Sts.eState := 5;
ELSIF fbStatus.Errorstop THEN    stAxis.Sts.eState := 6;
END_IF

// --- enable is a level, not an edge ---
fbPower(
    Axis          := Ref,
    Enable        := stAxis.Cmd.bEnable,
    Enable_Positive := stAxis.Cmd.bEnable,
    Enable_Negative := stAxis.Cmd.bEnable,
    Override      := 100.0
);

// --- edge-triggered commands ---
rExecute(CLK := stAxis.Cmd.bExecute);
rStop(CLK := stAxis.Cmd.bStop);
rReset(CLK := stAxis.Cmd.bReset);
rHome(CLK := stAxis.Cmd.bHome);

IF rReset.Q THEN
    fbReset(Axis := Ref, Execute := TRUE);
ELSE
    fbReset(Axis := Ref, Execute := FALSE);
END_IF

IF rExecute.Q AND NOT bBusy AND NOT stAxis.Sts.bError THEN
    eActive := stAxis.Cmd.eMode;
    bBusy   := TRUE;
END_IF

fbMoveAbs(
    Axis         := Ref,
    Execute      := bBusy AND (eActive = E_MoveMode.eAbsolute),
    Position     := stAxis.Cmd.fTarget,
    Velocity     := stAxis.Cmd.fVelocity,
    Acceleration := stAxis.Cmd.fAcceleration,
    Deceleration := stAxis.Cmd.fDeceleration
);

fbMoveRel(
    Axis         := Ref,
    Execute      := bBusy AND (eActive = E_MoveMode.eRelative),
    Distance     := stAxis.Cmd.fTarget,
    Velocity     := stAxis.Cmd.fVelocity,
    Acceleration := stAxis.Cmd.fAcceleration,
    Deceleration := stAxis.Cmd.fDeceleration
);

fbHome(Axis := Ref, Execute := rHome.Q);
fbStop(Axis := Ref, Execute := rStop.Q, Deceleration := stAxis.Cmd.fDeceleration);

// --- completion / fault bookkeeping ---
IF bBusy AND (fbMoveAbs.Done OR fbMoveRel.Done OR fbHome.Done) THEN
    stAxis.Sts.nSeq := stAxis.Sts.nSeq + 1;
    bBusy := FALSE;
END_IF

// A halt aborts the move without Done or Error; free the axis for the next command
IF bBusy AND (fbMoveAbs.CommandAborted OR fbMoveRel.CommandAborted OR fbHome.CommandAborted) THEN
    bBusy := FALSE;
END_IF

IF fbMoveAbs.Error OR fbMoveRel.Error OR fbStop.Error
   OR fbHome.Error OR fbPower.Error OR fbReset.Error THEN
    stAxis.Sts.bError := TRUE;
    bBusy := FALSE;
    IF fbMoveAbs.Error THEN        stAxis.Sts.nErrorId := fbMoveAbs.ErrorID;
    ELSIF fbMoveRel.Error THEN     stAxis.Sts.nErrorId := fbMoveRel.ErrorID;
    ELSIF fbStop.Error THEN        stAxis.Sts.nErrorId := fbStop.ErrorID;
    ELSIF fbHome.Error THEN        stAxis.Sts.nErrorId := fbHome.ErrorID;
    ELSIF fbPower.Error THEN       stAxis.Sts.nErrorId := fbPower.ErrorID;
    ELSE                           stAxis.Sts.nErrorId := fbReset.ErrorID;
    END_IF
END_IF

IF rReset.Q THEN
    stAxis.Sts.bError   := FALSE;
    stAxis.Sts.nErrorId := 0;
END_IF

// ===================== POU: MAIN (PROGRAM) =====================
PROGRAM MAIN
VAR
    fbAxis : ARRAY [1..24] OF FB_AxisServer;
    i      : INT;
END_VAR

FOR i := 1 TO GVL_Axes.nAxisCount DO
    fbAxis[i](stAxis := GVL_Axes.Axis[i], Ref := GVL_Axes.AxisRef[i]);
END_FOR
