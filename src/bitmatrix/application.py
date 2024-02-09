from pyteal import *
import beaker

class AppState:
    rights = beaker.state.LocalStateBlob(descr="Storage of rights", keys=16)


app = beaker.Application("SIAE", state = AppState())
app.apply(beaker.unconditional_opt_in_approval, initialize_local_state=True)

@app.external
def set_right(index: abi.Uint64, bit: abi.Uint64) -> Expr:
    byte = app.state.rights.read_byte(index.get() / Int(8))
    inbyte_index = (index.get() - Int(8) * (index.get() / Int(8)))

    return Seq([
        Assert(Eq(bit.get(), Int(0)).Or(Eq(bit.get(), Int(1)))),
        Assert(Lt(index.get(),app.state.rights.blob.max_keys * Int(8) * Int(127))),
        Assert(Neq(GetBit(byte, (Int(7) - inbyte_index)), bit.get())),
        app.state.rights.write_byte(index.get() / Int(8), SetBit(byte, (Int(7) - inbyte_index), bit.get()))
    ])
    
@app.external(read_only=True)
def get_right(index: abi.Uint64,*, output: abi.Uint64) -> Expr:
    byte = app.state.rights.read_byte(index.get() / Int(8))
    inbyte_index = (index.get() - Int(8) * (index.get() / Int(8)))
    
    return Seq([
        Assert(Lt(index.get(),app.state.rights.blob.max_keys * Int(8) * Int(127))),
        output.set(GetBit(byte, (Int(7) - inbyte_index)))
    ])
