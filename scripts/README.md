## Vectorwoks python scripts integration

1. Add this folder to VW: Tools / Plug-ins / Script Options / Enviroment Path

1. Install Python modules with `Marionette` / `uv`:
    ```sh
    #!/bin/zsh

    PY_MODULES=(numpy scipy geopy shapely debugpy)
    VW_PYTHON_PATH="$HOME/Library/Application Support/Vectorworks/2025/Python Externals"
    uv pip install $PY_MODULES --target $VW_PYTHON_PATH --python 3.9
    ```

1. in VW create minimal stubs like:
    ```python
    import vs

    try:
        import debugpy # setup remote debug server
        debugpy.listen(5678, in_process_debug_adapter=True)
    except ImportError: pass

    import work # script name without .py
    work.run()  # def run():... script entry point
    ```

1. Script cheatsheet:
    ```python
    import vs
    import sys
    import inspect
    from pprint import pformat

    def get_obj_info(obj: vs.Handle):
        return {'h': obj, 'type': obj.type, 'aux': obj.aux.type, 'parent': obj.parent.type}

    def vs_iter(container: vs.HandleContainer):
        child = container.first
        while child:
            yield child
            child = child.next

    def callback(obj: vs.Handle)
        # fill local variable with useful object types to inspect later
        obj_info = {'h': obj, 'type': obj.type, 'aux': obj.aux.type, 'parent': obj.parent.type}

        # inspect objects internal structure
        vs.AlrtDialog(f"{pformat(inspect.getmembers(obj))}")

        # object Records
        parametric_record = vs.GetParametricRecord(obj).name
        records = {}
        for rec in (vs.GetRecord(obj, i) for i in range(1, vs.NumRecords(obj) + 1)):
            records[rec.name] = {
                fld_name: vs.GetRField(obj, rec.name, fld_name)
                for fld_name in (vs.GetFldName(rec, j) for j in range(1, vs.NumFields(rec) + 1))
            }
        
        # container object types: Group(11), SymDef(16), Layer(31), PIO(86)
        if obj.type in (11, 16, 31, 86):
            # recursive walk thru object tree
            for child in vs_iter(obj):
                callback(child)

        # stop script execution and show local variables (like obj_info, records, ...)
        vs.AlrtDialog(f"{pformat(inspect.currentframe().f_locals, sort_dicts=False)}")

    def run():
        vs.Message(f"{sys.version}\n")      # show VW host python version
        vs.ForEachObject(callback, "VSEL")  # iterate thru selected objects

    if __name__ == "__main__":
        run()  # fallback when script pasted directly
    ```