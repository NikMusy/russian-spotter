"""Структуры разделяемой памяти Le Mans Ultimate.

Один в один с официальным SDK, который лежит прямо в игре:
  Le Mans Ultimate/Support/SharedMemoryInterface/
    - SharedMemoryInterface.hpp  (раскладка блока, имена объектов)
    - InternalsPlugin.hpp        (ScoringInfoV01, TelemInfoV01, ...)

Сторонний плагин не нужен: LMU публикует память сама.

ВАЖНО ПРО ВЫРАВНИВАНИЕ. В InternalsPlugin.hpp стоит #pragma pack(push, 4)
в начале (строка 24) и pack(pop) в конце (строка 1106). Поэтому:

  * структуры ИЗ InternalsPlugin.hpp (TelemVect3, TelemInfoV01,
    VehicleScoringInfoV01, ScoringInfoV01, ApplicationStateV01) - pack = 4;

  * структуры ИЗ SharedMemoryInterface.hpp (SharedMemory*) объявлены ПОСЛЕ
    того #include, то есть уже за pack(pop) - у них ОБЫЧНОЕ выравнивание.

Разница не косметическая: в SharedMemoryScoringData за ScoringInfoV01 (548
байт) идёт size_t. При обычном выравнивании он встаёт на 552, а не на 548,
и весь массив машин съезжает на 4 байта - имена пилотов читаются пустыми,
а координаты превращаются в 1e152.
"""

from __future__ import annotations

import ctypes
from ctypes import (
    c_bool, c_byte, c_char, c_double, c_float, c_int32, c_long, c_short,
    c_ubyte, c_uint8, c_uint32, c_ulong, c_ulonglong, c_ushort, c_void_p,
)

# Имена объектов из SharedMemoryInterface.hpp
SHARED_MEMORY_FILE = "LMU_Data"
SHARED_MEMORY_EVENT = "LMU_Data_Event"

MAX_VEHICLES = 104          # размер массивов в SDK
MAX_PATH = 260
SME_MAX = 16                # SME_ENTER..SME_FFB
SCORING_STREAM = 65536

# Индексы в generic.events
SME_UPDATE_SCORING = 10
SME_UPDATE_TELEMETRY = 11


class Base(ctypes.Structure):
    """Структуры из InternalsPlugin.hpp - они внутри #pragma pack(push, 4)."""
    _pack_ = 4


class SharedBase(ctypes.Structure):
    """Структуры из SharedMemoryInterface.hpp - они уже за pack(pop),
    поэтому выравнивание обычное. _pack_ тут ставить НЕЛЬЗЯ."""


class TelemVect3(Base):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]


class TelemWheelV01(Base):
    _fields_ = [
        ("mSuspensionDeflection", c_double),
        ("mRideHeight", c_double),
        ("mSuspForce", c_double),
        ("mBrakeTemp", c_double),
        ("mBrakePressure", c_double),
        ("mRotation", c_double),
        ("mLateralPatchVel", c_double),
        ("mLongitudinalPatchVel", c_double),
        ("mLateralGroundVel", c_double),
        ("mLongitudinalGroundVel", c_double),
        ("mCamber", c_double),
        ("mLateralForce", c_double),
        ("mLongitudinalForce", c_double),
        ("mTireLoad", c_double),
        ("mGripFract", c_double),
        ("mPressure", c_double),
        ("mTemperature", c_double * 3),
        ("mWear", c_double),
        ("mTerrainName", c_char * 16),
        ("mSurfaceType", c_ubyte),
        ("mFlat", c_bool),
        ("mDetached", c_bool),
        ("mStaticUndeflectedRadius", c_ubyte),
        ("mVerticalTireDeflection", c_double),
        ("mWheelYLocation", c_double),
        ("mToe", c_double),
        ("mTireCarcassTemperature", c_double),
        ("mTireInnerLayerTemperature", c_double * 3),
        ("mOptimalTemp", c_float),
        ("mCompoundIndex", c_ubyte),
        ("mCompoundType", c_ubyte),
        ("mExpansion", c_ubyte * 18),
    ]


class TelemInfoV01(Base):
    _fields_ = [
        ("mID", c_long),
        ("mDeltaTime", c_double),
        ("mElapsedTime", c_double),
        ("mLapNumber", c_long),
        ("mLapStartET", c_double),
        ("mVehicleName", c_char * 64),
        ("mTrackName", c_char * 64),

        ("mPos", TelemVect3),
        ("mLocalVel", TelemVect3),
        ("mLocalAccel", TelemVect3),
        ("mOri", TelemVect3 * 3),
        ("mLocalRot", TelemVect3),
        ("mLocalRotAccel", TelemVect3),

        ("mGear", c_long),
        ("mEngineRPM", c_double),
        ("mEngineWaterTemp", c_double),
        ("mEngineOilTemp", c_double),
        ("mClutchRPM", c_double),

        ("mUnfilteredThrottle", c_double),
        ("mUnfilteredBrake", c_double),
        ("mUnfilteredSteering", c_double),
        ("mUnfilteredClutch", c_double),

        ("mFilteredThrottle", c_double),
        ("mFilteredBrake", c_double),
        ("mFilteredSteering", c_double),
        ("mFilteredClutch", c_double),

        ("mSteeringShaftTorque", c_double),
        ("mFront3rdDeflection", c_double),
        ("mRear3rdDeflection", c_double),

        ("mFrontWingHeight", c_double),
        ("mFrontRideHeight", c_double),
        ("mRearRideHeight", c_double),
        ("mDrag", c_double),
        ("mFrontDownforce", c_double),
        ("mRearDownforce", c_double),

        ("mFuel", c_double),
        ("mEngineMaxRPM", c_double),
        ("mScheduledStops", c_ubyte),
        ("mOverheating", c_bool),
        ("mDetached", c_bool),
        ("mHeadlights", c_bool),
        ("mDentSeverity", c_ubyte * 8),
        ("mLastImpactET", c_double),
        ("mLastImpactMagnitude", c_double),
        ("mLastImpactPos", TelemVect3),

        ("mEngineTorque", c_double),
        ("mCurrentSector", c_long),
        ("mSpeedLimiter", c_ubyte),
        ("mMaxGears", c_ubyte),
        ("mFrontTireCompoundIndex", c_ubyte),
        ("mRearTireCompoundIndex", c_ubyte),
        ("mFuelCapacity", c_double),
        ("mFrontFlapActivated", c_ubyte),
        ("mRearFlapActivated", c_ubyte),
        ("mRearFlapLegalStatus", c_ubyte),
        ("mIgnitionStarter", c_ubyte),

        ("mFrontTireCompoundName", c_char * 18),
        ("mRearTireCompoundName", c_char * 18),

        ("mSpeedLimiterAvailable", c_ubyte),
        ("mAntiStallActivated", c_ubyte),
        ("mUnused", c_ubyte * 2),
        ("mVisualSteeringWheelRange", c_float),

        ("mRearBrakeBias", c_double),
        ("mTurboBoostPressure", c_double),
        ("mPhysicsToGraphicsOffset", c_float * 3),
        ("mPhysicalSteeringWheelRange", c_float),

        ("mDeltaBest", c_double),
        ("mBatteryChargeFraction", c_double),

        ("mElectricBoostMotorTorque", c_double),
        ("mElectricBoostMotorRPM", c_double),
        ("mElectricBoostMotorTemperature", c_double),
        ("mElectricBoostWaterTemperature", c_double),
        ("mElectricBoostMotorState", c_ubyte),
        ("mLapInvalidated", c_bool),
        ("mABSActive", c_bool),
        ("mTCActive", c_bool),
        ("mSpeedLimiterActive", c_bool),
        ("mWiperState", c_uint8),
        ("mTC", c_uint8),
        ("mTCMax", c_uint8),
        ("mTCSlip", c_uint8),
        ("mTCSlipMax", c_uint8),
        ("mTCCut", c_uint8),
        ("mTCCutMax", c_uint8),
        ("mABS", c_uint8),
        ("mABSMax", c_uint8),
        ("mMotorMap", c_uint8),
        ("mMotorMapMax", c_uint8),
        ("mMigration", c_uint8),
        ("mMigrationMax", c_uint8),
        ("mFrontAntiSway", c_uint8),
        ("mFrontAntiSwayMax", c_uint8),
        ("mRearAntiSway", c_uint8),
        ("mRearAntiSwayMax", c_uint8),
        ("mLiftAndCoastProgress", c_uint8),
        ("mTrackLimitsSteps", c_uint8),
        ("mRegen", c_float),
        ("mSoC", c_float),
        ("mVirtualEnergy", c_float),
        ("mTimeGapCarAhead", c_float),
        ("mTimeGapCarBehind", c_float),
        ("mTimeGapPlaceAhead", c_float),
        ("mTimeGapPlaceBehind", c_float),
        ("mVehicleModel", c_char * 30),
        ("mVehicleClass", c_uint8),          # IP_VehicleClass
        ("mVehicleChampionship", c_uint8),   # IP_VehicleChampionship

        ("mExpansion", c_ubyte * 20),
        ("mWheel", TelemWheelV01 * 4),
    ]


class VehicleScoringInfoV01(Base):
    _fields_ = [
        ("mID", c_long),
        ("mDriverName", c_char * 32),
        ("mVehicleName", c_char * 64),
        ("mTotalLaps", c_short),
        ("mSector", c_byte),
        ("mFinishStatus", c_byte),
        ("mLapDist", c_double),
        ("mPathLateral", c_double),
        ("mTrackEdge", c_double),

        ("mBestSector1", c_double),
        ("mBestSector2", c_double),
        ("mBestLapTime", c_double),
        ("mLastSector1", c_double),
        ("mLastSector2", c_double),
        ("mLastLapTime", c_double),
        ("mCurSector1", c_double),
        ("mCurSector2", c_double),

        ("mNumPitstops", c_short),
        ("mNumPenalties", c_short),
        ("mIsPlayer", c_bool),

        ("mControl", c_byte),
        ("mInPits", c_bool),
        ("mPlace", c_ubyte),
        ("mVehicleClass", c_char * 32),

        ("mTimeBehindNext", c_double),
        ("mLapsBehindNext", c_long),
        ("mTimeBehindLeader", c_double),
        ("mLapsBehindLeader", c_long),
        ("mLapStartET", c_double),

        ("mPos", TelemVect3),
        ("mLocalVel", TelemVect3),
        ("mLocalAccel", TelemVect3),

        ("mOri", TelemVect3 * 3),
        ("mLocalRot", TelemVect3),
        ("mLocalRotAccel", TelemVect3),

        ("mHeadlights", c_ubyte),
        ("mPitState", c_ubyte),
        ("mServerScored", c_ubyte),
        ("mIndividualPhase", c_ubyte),

        ("mQualification", c_long),
        ("mTimeIntoLap", c_double),
        ("mEstimatedLapTime", c_double),

        ("mPitGroup", c_char * 24),
        ("mFlag", c_ubyte),
        ("mUnderYellow", c_bool),
        ("mCountLapFlag", c_ubyte),
        ("mInGarageStall", c_bool),

        ("mUpgradePack", c_ubyte * 16),
        ("mPitLapDist", c_float),

        ("mBestLapSector1", c_float),
        ("mBestLapSector2", c_float),

        ("mSteamID", c_ulonglong),
        ("mVehFilename", c_char * 32),
        ("mAttackMode", c_short),
        ("mFuelFraction", c_ubyte),
        ("mDRSState", c_bool),
        ("mExpansion", c_ubyte * 4),
    ]


class ScoringInfoV01(Base):
    _fields_ = [
        ("mTrackName", c_char * 64),
        ("mSession", c_long),
        ("mCurrentET", c_double),
        ("mEndET", c_double),
        ("mMaxLaps", c_long),
        ("mLapDist", c_double),
        ("mResultsStream", c_void_p),      # указатель, в нашей копии не годен

        ("mNumVehicles", c_long),
        ("mGamePhase", c_ubyte),
        ("mYellowFlagState", c_byte),
        ("mSectorFlag", c_byte * 3),
        ("mStartLight", c_ubyte),
        ("mNumRedLights", c_ubyte),
        ("mInRealtime", c_bool),
        ("mPlayerName", c_char * 32),
        ("mPlrFileName", c_char * 64),

        ("mDarkCloud", c_double),
        ("mRaining", c_double),
        ("mAmbientTemp", c_double),
        ("mTrackTemp", c_double),
        ("mWind", TelemVect3),
        ("mMinPathWetness", c_double),
        ("mMaxPathWetness", c_double),

        ("mGameMode", c_ubyte),
        ("mIsPasswordProtected", c_bool),
        ("mServerPort", c_ushort),
        ("mServerPublicIP", c_ulong),
        ("mMaxPlayers", c_long),
        ("mServerName", c_char * 32),
        ("mStartET", c_float),

        ("mAvgPathWetness", c_double),
        ("mSessionTimeRemaining", c_float),
        ("mTimeOfDay", c_float),
        ("mIsFixedSetup", c_bool),
        ("mTrackGripLevel", c_uint8),
        ("mCloudCoverage", c_uint8),
        ("mTrackLimitsStepsPerPenalty", c_uint8),
        ("mTrackLimitsStepsPerPoint", c_uint8),
        ("mExpansion", c_ubyte * 187),

        ("mVehicle", c_void_p),            # указатель, в нашей копии не годен
    ]


class ApplicationStateV01(Base):
    _fields_ = [
        ("mAppWindow", c_void_p),          # HWND
        ("mWidth", c_ulong),
        ("mHeight", c_ulong),
        ("mRefreshRate", c_ulong),
        ("mWindowed", c_ulong),
        ("mOptionsLocation", c_ubyte),
        ("mOptionsPage", c_char * 31),
        ("mExpansion", c_ubyte * 204),
    ]


class SharedMemoryGeneric(SharedBase):
    _fields_ = [
        ("events", c_uint32 * SME_MAX),
        ("gameVersion", c_long),
        ("FFBTorque", c_float),
        ("appInfo", ApplicationStateV01),
    ]


class SharedMemoryPathData(SharedBase):
    _fields_ = [
        ("userData", c_char * MAX_PATH),
        ("customVariables", c_char * MAX_PATH),
        ("stewardResults", c_char * MAX_PATH),
        ("playerProfile", c_char * MAX_PATH),
        ("pluginsFolder", c_char * MAX_PATH),
    ]


class SharedMemoryScoringData(SharedBase):
    _fields_ = [
        ("scoringInfo", ScoringInfoV01),
        # Тут и ломалось: size_t хочет выравнивание 8, поэтому встаёт на
        # 552, а не сразу за ScoringInfoV01 (548).
        ("scoringStreamSize", ctypes.c_size_t),
        ("vehScoringInfo", VehicleScoringInfoV01 * MAX_VEHICLES),
        ("scoringStream", c_char * SCORING_STREAM),
    ]


class SharedMemoryTelemetryData(SharedBase):
    _fields_ = [
        ("activeVehicles", c_uint8),
        ("playerVehicleIdx", c_uint8),
        ("playerHasVehicle", c_bool),
        ("telemInfo", TelemInfoV01 * MAX_VEHICLES),
    ]


class SharedMemoryObjectOut(SharedBase):
    _fields_ = [
        ("generic", SharedMemoryGeneric),
        ("paths", SharedMemoryPathData),
        ("scoring", SharedMemoryScoringData),
        ("telemetry", SharedMemoryTelemetryData),
    ]


class SharedMemoryLayout(SharedBase):
    _fields_ = [("data", SharedMemoryObjectOut)]


LAYOUT_SIZE = ctypes.sizeof(SharedMemoryLayout)


# --- значения из заголовка -------------------------------------------

class GamePhase:
    BEFORE_SESSION = 0
    RECON = 1
    GRID_WALK = 2
    FORMATION = 3
    COUNTDOWN = 4
    GREEN = 5
    FULL_COURSE_YELLOW = 6
    STOPPED = 7
    OVER = 8
    PAUSED = 9


class YellowState:
    INVALID = -1
    NONE = 0
    PENDING = 1
    PITS_CLOSED = 2
    PIT_LEAD_LAP = 3
    PITS_OPEN = 4
    LAST_LAP = 5
    RESUME = 6
    RACE_HALT = 7


class VehFlag:
    GREEN = 0
    BLUE = 6


class PitState:
    NONE = 0
    REQUEST = 1
    ENTERING = 2
    STOPPED = 3
    EXITING = 4


class Control:
    NOBODY = -1
    LOCAL_PLAYER = 0
    LOCAL_AI = 1
    REMOTE = 2
    REPLAY = 3


# Классы машин из IP_VehicleClass (начало InternalsPlugin.hpp).
class VehicleClass:
    HYPERCAR = 0x00
    LMP2_ELMS = 0x02
    LMP2 = 0x03
    LMP3 = 0x04
    GTE = 0x05
    GT3 = 0x06
    PACE_CAR = 0x08
    UNKNOWN = 0xFF


# Кто кого быстрее: для реплик про трафик классов.
CLASS_SPEED_ORDER = {
    VehicleClass.HYPERCAR: 4,
    VehicleClass.LMP2: 3,
    VehicleClass.LMP2_ELMS: 3,
    VehicleClass.LMP3: 2,
    VehicleClass.GTE: 1,
    VehicleClass.GT3: 1,
}

PROTOTYPE_CLASSES = {
    VehicleClass.HYPERCAR, VehicleClass.LMP2, VehicleClass.LMP2_ELMS,
    VehicleClass.LMP3,
}
GT_CLASSES = {VehicleClass.GTE, VehicleClass.GT3}
