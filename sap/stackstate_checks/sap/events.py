class Events:
    # SAP_ITSAMInstance/Alert
    ccms_alerts = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate",
                     "field": "field is mandatory: Name of field with value"},  # example entry
        "Oracle|Performance|Locks": {"field": "Value"},
        "R3Services|Dialog|ResponseTimeDialog": {"field": "ActualValue"},
        "R3Services|Spool": {"description": "SAP:Spool utilization",
                             "field": "ActualValue"},
        "R3Services|Spool|SpoolService|ErrorsInWpSPO": {"description": "SAP:ErrorsInWpSPO",
                                                        "field": "ActualValue"},
        "R3Services|Spool|SpoolService|ErrorFreqInWpSPO": {"description": "SAP:ErrorsFreqInWpSPO",
                                                           "field": "ActualValue"},
        "Shortdumps Frequency": {"field": "ActualValue"}
        }

    # SAP_ITSAMInstance/Parameter
    instance_events = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate"}  # example entry
    }

    # SAP_ITSAMDatabaseMetric
    dbmetric_events = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate"},  # example entry
        "db.ora.tablespace.status": {"field": "Value"},
        "35": {"description": "HDB:Backup_exist",
               "field": "Value"},
        "36": {"description": "HDB:Recent_backup",
               "field": "Value"},
        "38": {"description": "HDB:Recent_log_backup",
               "field": "Value"},
        "102": {"description": "HDB:System_backup_Exists",
                "field": "Value"},
        "1015": {"description": "HDB:System replication",
                 "field": "Value"}
    }

    # GetComputerSystem
    system_events = {
        "SAP name": {"description": "description is optional: Alternative name for stackstate"}  # example entry
        }
