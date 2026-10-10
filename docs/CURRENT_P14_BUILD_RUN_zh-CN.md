# 原七任务／P14 的独立构建与运行合同

该入口不属于四家 `register-installation.py` 服务，不使用它们的 installation-record，也不把四家镜像传给旧七任务。它使用冻结588份科学来源、独立 Dockerfile 和当次镜像身份。实际需要已有 Docker Linux/amd64 与 PowerShell7.3+；文档不安装工具或升级系统。

```powershell
.\scripts\build-docker.ps1 -Tag ai4orgchem-runtime:p14-local
.\scripts\run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

上述是操作形式，本轮未执行构建或任务。构建应在干净、身份固定的 Runtime 源码中进行；镜像与结果不得继承旧科学 PASS。其他任务的协议、资源、前序输出和授权仍按 [运行合同](RUN_zh-CN.md) 核对。无效镜像或科学资格必须拒绝。原 P01—P14 不因新增用户入口的失败自动重审；L4 不支持恢复运行。
