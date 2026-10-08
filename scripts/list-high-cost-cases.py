from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.high_cost_cases import units,limits
print(json.dumps({'schema':'high-cost-capabilities-v1','units':units(),'resources':{c:limits(c,'live') for c in ['P11','P12']},'scientific_validation':'SEE_MEASURED_SUPPORT_MATRIX','general_user_conditional_compute':'BLOCKED','resume':False},ensure_ascii=False,indent=2))
