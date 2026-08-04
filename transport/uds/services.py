try:
    from udsoncan.services import (
        DiagnosticSessionControl,
        TesterPresent,
        RequestDownload,
        TransferData,
        RequestTransferExit,
        ECUReset
    )
    UDSCAN_AVAILABLE = True
except ImportError:
    DiagnosticSessionControl = "DiagnosticSessionControl"
    TesterPresent = "TesterPresent"
    RequestDownload = "RequestDownload"
    TransferData = "TransferData"
    RequestTransferExit = "RequestTransferExit"
    ECUReset = "ECUReset"
    UDSCAN_AVAILABLE = False

SESSION_PROGRAMMING = 0x02

SID = {
    "DiagnosticSessionControl": DiagnosticSessionControl,
    "TesterPresent": TesterPresent,
    "RequestDownload": RequestDownload,
    "TransferData": TransferData,
    "RequestTransferExit": RequestTransferExit,
    "ECUReset": ECUReset
}
