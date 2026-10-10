"""Spawned worker entry. No Qt UI imports, no giant result transfer over IPC."""
import traceback


def run_job(kind,args,queue,cancel):
    try:
        if kind=="index":
            from .layout_source import index_layout
            result=index_layout(args["path"])
        elif kind=="extract":
            from .layout_source import extract_layout
            result=extract_layout(args["path"],args["database"],args["options"],lambda message:queue.put(("progress",message)),cancel.is_set)
        elif kind=="export":
            from .dataset import export_library
            result=export_library(args["database"],args["directory"],args.get("ids"),lambda m:queue.put(("progress",m)),cancel.is_set)
        else:raise ValueError("未知后台任务")
        queue.put(("done",result))
    except BaseException as exc:
        queue.put(("error",f"{exc}"));queue.put(("trace",traceback.format_exc()))
