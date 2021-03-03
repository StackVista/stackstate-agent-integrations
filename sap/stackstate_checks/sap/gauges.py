class Gauges:
    # SAP_ITSAMDatabaseMetric
    dbmetric_gauges = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate",
                     "field": "field is mandatory: Name of field with value"},  # example entry
        "10": {"description": "HDB:Delta merges",
               "field": "Value"},
        "sap.hdb.alert.license_expiring": {"field": "Value"},  # was 31
        "sap.hdb.alert.backup.data.last": {"field": "Value"},  # was 37
        "USED_DATA_AREA": {"description": "MAXDB:USED_DATA_AREA",
                           "field": "Value"},
        "USED_LOG_AREA": {"description": "MAXDB:USED_LOG_AREA",
                          "field": "Value"},
        "db.ora.tablespace.free": {"field": "Value"},
        "TimeToLicenseExpiry": {"description": "syb:TimeToLicenseExpiry",
                                "field": "Value"}
        }

    # SAP_ITSAMInstance/Parameter
    instance_gauges = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate"},  # example entry
        "PHYS_MEMSIZE": {"description": "phys_memsize"}
        }

    # GetComputerSystem
    system_gauges = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate"},  # example entry
        "FreeSpaceInPagingFiles": {"description": "SAP:FreeSpaceInPagingFiles"},
        "SizeStoredInPagingFiles": {"description": "SAP:sizeStoredInPagingFiles"},
        "TotalSwapSpaceSize": {"description": "SAP:TotalSwapSpaceSize"}
        }
