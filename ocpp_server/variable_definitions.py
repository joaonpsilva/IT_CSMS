from ocpp.v201 import datatypes

component_DeviceDataCtrlr = datatypes.ComponentType(
    name="DeviceDataCtrlr"
)
component_MonitoringCtrlr = datatypes.ComponentType(
    name="MonitoringCtrlr"
)
component_LocalAuthListCtrlr = datatypes.ComponentType(
    name="LocalAuthListCtrlr"
)

VARIABLES ={
    "ItemsPerMessageGetVariables" : {
        "component" : component_DeviceDataCtrlr,
        "variable" : datatypes.VariableType(
            name="ItemsPerMessage",
            instance="GetVariables"
        )            
    },
    "ItemsPerMessageSetVariables" : {
        "component" : component_DeviceDataCtrlr,
        "variable" : datatypes.VariableType(
            name="ItemsPerMessage",
            instance="SetVariables"
        )            
    },
    "BytesPerMessageSetVariableMonitoring" : {
        "component" : component_MonitoringCtrlr,
        "variable" : datatypes.VariableType(
            name="BytesPerMessage",
            instance="SetVariableMonitoring"
        )
    },
    "ItemsPerMessageSetVariableMonitoring" : {
        "component" : component_MonitoringCtrlr,
        "variable" : datatypes.VariableType(
            name="ItemsPerMessage",
            instance="SetVariableMonitoring"
        )
    },
    "ItemsPerMessageClearVariableMonitoring" : {
        "component" : component_MonitoringCtrlr,
        "variable" : datatypes.VariableType(
            name="ItemsPerMessage",
            instance="ClearVariableMonitoring"
        )
    },
    "BytesPerMessageClearVariableMonitoring" : {
        "component" : component_MonitoringCtrlr,
        "variable" : datatypes.VariableType(
            name="BytesPerMessage",
            instance="ClearVariableMonitoring"
        )
    },
    "ItemsPerMessageSendLocalList" : {
        "component" : component_LocalAuthListCtrlr,
        "variable" : datatypes.VariableType(
            name="ItemsPerMessage"
        )
    },
    "BytesPerMessageSendLocalList" : {
        "component" : component_LocalAuthListCtrlr,
        "variable" : datatypes.VariableType(
            name="BytesPerMessage"
        )
    }
}