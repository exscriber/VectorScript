## Tool [modernize.py](modernize.py)

### Enhance `vs.py` file with several IDE-friedly modern features
1. Class methods decorated with `@property`: can only be called `h.type` as it shoud
1. Composite data types like `Vector3`: syntactic sugar for tuples
1. Functions with type annotated args and returns
1. Docstring lines ends up with two spaces (markdown newline)
1. Reorder of docstring structure: Description came first, everything else - below
1. See-also function links to navigate thru

### Info gathering
Appears there is no single point of truth in **VectorScript** definitions...  
So we gather relevant pieces from several different places:
1. **Arg** types from `vs.py` trailing comments: `# REAL - Real number.`
1. **Return** types from `vs.py` pascal docstring: `VectorScript: FUNCTION Abs(v:REAL) : REAL;`
1. **See-also** links and **Deprecated** status from `VectorScript Reference.xml`

### Inconsistancy
There is some hacks to work around data inconsistancy:
1. Class method types hardcoded: seems there is no data to derive from...
1. Funcs with extra phantom return in **Python** docstrings: corrected from **VectorScript** counterparts...  
    `CreateDataVisPDMenu, CreateStyledStatic, GetDrawingArea, GetGradientDataN, GetLBItemMkrChoice,PopupGetChoices, RefreshResManager, RunImageComp, SetLBItemByClass, SetLBItemMkrChoice, SetParamStyleType`
1. Funcs with variadic arg: marked as *arg  
    `Concat, Message, Poly, Poly3D, Write, WriteBin, WriteLn, WriteLnMac, WriteMac`  
    `GS_EdSh_ConstructLayout`: not marked because it has 3 variadic args - not possible in python
1. Funcs with wrong arg types:  
    `Poly`: must be `POINT` instead of `REAL`  
    `Poly3D`: must be `POINT3D` instead of `REAL`
