"""Conservative capacity admission; never changes WSL or evicts other workloads."""
import ctypes, math, os, shutil
from pathlib import Path

def host_memory():
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),('page_total',ctypes.c_ulonglong),('page_available',ctypes.c_ulonglong),('virtual_total',ctypes.c_ulonglong),('virtual_available',ctypes.c_ulonglong),('extended_available',ctypes.c_ulonglong)]
        m=Memory();m.length=ctypes.sizeof(m)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise OSError('Windows memory observation unavailable')
        return {'total_bytes':int(m.total),'available_bytes':int(m.available),'source':'Windows GlobalMemoryStatusEx'}
    values={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k,v=line.split(':',1);values[k]=int(v.split()[0])*1024
    return {'total_bytes':values['MemTotal'],'available_bytes':values['MemAvailable'],'source':'host /proc/meminfo'}
def admission(resources,engine,guest,host,disk_free,*,live=True):
    reasons=[];reserve=2147483648 if live else 536870912
    def positive(v):return type(v) is int and v>0
    for obj,k in [(engine,'NCPU'),(engine,'MemTotal'),(guest,'available_bytes'),(host,'available_bytes')]:
        if not isinstance(obj,dict) or not positive(obj.get(k)):reasons.append('UNKNOWN_'+k)
    if type(disk_free) is not int or disk_free<0:reasons.append('UNKNOWN_DISK_FREE')
    if reasons:return {'status':'BLOCKED_RESOURCE_UNKNOWN','reasons':reasons}
    if engine['NCPU']<resources['cpus']:reasons.append('ENGINE_CPU_LIMIT_TOO_SMALL')
    if engine['MemTotal']<resources['memory_bytes']+1073741824:reasons.append('ENGINE_MEMORY_PLUS_RESERVE_TOO_SMALL')
    if guest['available_bytes']<resources['memory_bytes']+1073741824:reasons.append('GUEST_AVAILABLE_MEMORY_PLUS_RESERVE_TOO_SMALL')
    if host['available_bytes']<resources['memory_bytes']+reserve:reasons.append('HOST_AVAILABLE_MEMORY_PLUS_RESERVE_TOO_SMALL')
    if disk_free<resources['scratch_bytes_required']+1073741824:reasons.append('SCRATCH_DISK_SPACE_TOO_SMALL')
    return {'status':'PASS' if not reasons else 'BLOCKED_RESOURCE_CAPACITY','reasons':reasons,'resources':resources,'host':host,'engine':engine,'guest':guest,'disk_free_bytes':disk_free,'host_reserve_bytes':reserve,'does_not_modify_global_configuration':True,'does_not_stop_other_processes':True}
