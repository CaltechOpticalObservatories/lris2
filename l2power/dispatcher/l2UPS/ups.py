# Library for the APC UPS with SNMP v1 communication

import configparser

import DFW

from . import snmp

class UPS:
    
    def __init__(self, service, config_file):
        
        self.service = service
        self.config_file = config_file
        self.periods = dict()
        
        self.polling = False
        self.failures = 0
        self.failure_threshold = 6
        
        # Variables populated by config file
        self.snmp_host = None
        self.snmp_read = None
        self.snmp_write = None
        
        self.config = configparser.ConfigParser()
        self.parseConfigFile()
        self.checkSanity()
        
        self.snmp_object = snmp.Commands(self.snmp_host, self.snmp_read, self.snmp_write)
        
    def parseConfigFile(self):
        
        if self.config_file is None:
            return
        
        self.config.read(self.config_file)
        
        self.snmp_host = self.config.get('snmp', 'hostname')
        self.snmp_read = self.config.get('snmp', 'read')
        self.snmp_write = self.config.get('snmp', 'write')
        
    def checkSanity(self):
        """ 
        Raise exceptions if something is wrong with the runtime
        configuration, as specified by the configuration file and
        on the command line.
        """
        
        if self.config_file is None:
            raise ValueError('no configuration file specified')
        
        sections = ('main', 'snmp')
        
        for section in sections:
            if self.config.has_section(section):
                pass
            else:
                raise configparser.NoSectionError("[%s]" & (section))
            
        self.config.get('main', 'service')
        self.config.get('main', 'stdiosvc')
        
    def setupKeywords(self):
        
        service = self.service
        periods = self.periods
        # snmp = self.snmp_object
        
        disp_num = 1
        
        # UPS Keywords
        prefix = "UPS%d" % (disp_num)
        DFW.Keyword.String(prefix + 'ADDRESS', service, self.snmp_host)
        
        # Battery Sensors
        battery_cap_oid = ".1.3.6.1.4.1.318.1.1.1.2.3.1.0"
        battery_temp_oid = ".1.3.6.1.4.1.318.1.1.1.2.3.2.0"
        battery_vol_oid = ".1.3.6.1.4.1.318.1.1.1.2.3.4.0"
        
        battery_cap_key = prefix + "CAPBAT"
        periods[battery_cap_key] = 2
        battery_temp_key = prefix + "TEMPBAT"
        periods[battery_temp_key] = 2
        battery_vol_key = prefix + "VOLTBAT"
        periods[battery_vol_key] = 2
        
        snmp.Double(battery_cap_key, service, self, battery_cap_oid, periods[battery_cap_key])
        snmp.Double(battery_temp_key, service, self, battery_temp_oid, periods[battery_temp_key])
        snmp.Double(battery_vol_key, service, self, battery_vol_oid, periods[battery_vol_key])
        
        # Input Sensors
        input_vol_oid = ".1.3.6.1.4.1.318.1.1.1.3.3.1.0"
        input_freq_oid = ".1.3.6.1.4.1.318.1.1.1.3.3.4.0"
        
        input_vol_key = prefix + "VOLIN"
        periods[input_vol_key] = 2
        input_frequency_key = prefix + "FREQIN"
        periods[input_frequency_key] = 2
        
        snmp.Double(input_vol_key, service, self, input_vol_oid, periods[input_vol_key])
        snmp.Double(input_frequency_key, service, self, input_freq_oid, periods[input_frequency_key])
        
        # Output Sensors
        output_vol_oid = ".1.3.6.1.4.1.318.1.1.1.4.3.1.0"
        output_freq_oid = ".1.3.6.1.4.1.318.1.1.1.4.3.2.0"
        output_load_oid = ".1.3.6.1.4.1.318.1.1.1.4.3.3.0"
        output_amp_oid = ".1.3.6.1.4.1.318.1.1.1.4.3.4.0"
        output_kwh_oid = ".1.3.6.1.4.1.318.1.1.1.4.3.6.0" # 2 decimal precision
        
        output_vol_key = prefix + "VOLOUT"
        periods[output_vol_key] = 2
        output_freq_key = prefix + "FRQOUT"
        periods[output_freq_key] = 2
        output_load_key = prefix + "LOADOUT"
        periods[output_load_key] = 2
        output_amp_key = prefix + "AMPOUT"
        periods[output_amp_key] = 2
        output_kwh_key = prefix + "KWHOUT"
        periods[output_kwh_key] = 2
 
        snmp.Double(output_vol_key, service, self, output_vol_oid, periods[output_vol_key])
        snmp.Double(output_freq_key, service, self, output_freq_oid, periods[output_freq_key])
        snmp.Double(output_load_key, service, self, output_load_oid, periods[output_load_key])
        snmp.Double(output_amp_key, service, self, output_amp_oid, periods[output_amp_key])
        snmp.Double(output_kwh_key, service, self, output_kwh_oid, periods[output_kwh_key])
        
    def getOverallStatus(self):
        """ Return the current SNMP status (online, refusing snmp, etc.) for
            this UPS. Return None if status is not available.
        """

        status = "UPS_SNMP"

        try:
            status = self.service[status]
        except KeyError:
            return

        if status.value is None:
            return

        current_status = status.mapped(lower=True)
        return current_status

 # end of class UPS
