from pyteal import *
import beaker
from typing import Literal as L
LEFT_PREFIX = Int(0)

class AppState:
    rights = beaker.state.LocalStateBlob(descr="Storage of rights", keys=16)
    deault_root = beaker.state.GlobalStateValue(stack_type=TealType.bytes)

app = beaker.Application("SIAE", state = AppState())
app.apply(beaker.unconditional_opt_in_approval, initialize_local_state=True)


@app.create
def create(deafult_root: abi.DynamicBytes) -> Expr:
    return Seq([app.state.deault_root.set(deafult_root.get())])

@app.external
def get_root(index: abi.Uint64,*,output: abi.DynamicBytes) -> Expr:
    return Seq([output.set(internal_get_root(index)),
                If(Eq(output.get(),Bytes('base16','0x'+'0'*64))).Then(output.set(app.state.deault_root.get())),
        ])

@app.external
def set_root(index: abi.Uint64,new_root: abi.DynamicBytes) -> Expr:
    stateless_new_root = Extract(Gtxn[0].note(), Int(0), Int(32))
    stateless_old_root = Extract(Gtxn[0].note(), Int(32), Int(32))
    STATELESS_SC_ADDR = Addr("7UXWWDHIWYOO2LGXTI2FRJYDFHIMPUTUKHN5FLSI5CPCGLHA3DCNKWEMFU")
    start_index = index.get() * Int(32)

    old_root = ScratchVar(TealType.bytes)

    return Seq([
        old_root.store(internal_get_root(index)),
        If(Eq(old_root.load(),Bytes('base16','0x'+'0'*64))).Then(old_root.store(app.state.deault_root.get())),
        Assert(Eq(new_root.get(), stateless_new_root)),
        Assert(Eq(old_root.load(), stateless_old_root)),
        Assert(Eq(Gtxn[0].receiver(), Gtxn[1].sender())),
        Assert(Gtxn[0].sender() == STATELESS_SC_ADDR),
        Assert(Lt(index.get(),app.state.rights.blob.max_bytes / Int(32))),
        app.state.rights.write(start_index, new_root.get())
    ])

@Subroutine(TealType.bytes)
def internal_get_root(index: abi.Uint64) -> Expr:
    # roots are (keys*127)\32 and index start from 0
    # so if we have 8 keys can get at most the root numer 30 because is the 31th root
    start_index = index.get() * Int(32)
    return Seq ([Assert(Lt(index.get(),app.state.rights.blob.max_bytes / Int(32))),
                 Return(app.state.rights.read(start_index, start_index + Int(32)))])



################# STATELESS #################

def calculate_root() -> Expr:
    """
    Given a leaf and a path, along with the length of the path, and the new and old root, it calculates the new root and checks if it is equal to the new root.
    Morover, it checks if the old root is equal to the old root. Finally, it checks if the note is equal to the new root||old root.
    :param leaf: The leaf to start from.
    :param path: The path to the leaf. That is composed of the nodes from the leaf to the root, of 33 bytes each. The first byte is the prefix (0 for left, 1 for right).
    :param path_length: The length of the path.
    :param new_root: The new root to check against.
    :param old_root: The old root to check against.
    """
    insert = Arg(0)
    old_leaf = Arg(1)
    leaf = BytesXor(insert, old_leaf)

    path = Arg(2)
    path_length = Len(path) / Int(33)
    new_root = Arg(3)
    old_root = Arg(4)

    result = ScratchVar(TealType.bytes)
    old_result = ScratchVar(TealType.bytes)
    i = ScratchVar(TealType.uint64)

    path_node = abi.make(abi.StaticBytes[L[33]])
    return Seq ([Assert(Eq(BytesAnd(old_leaf, insert), Bytes('\x00'*28))),
                 result.store(Sha256(leaf)),
                 old_result.store(Sha256(old_leaf)),

                 For(i.store(Int(0)), i.load() < path_length, i.store(i.load() + Int(1))).Do(
                        path_node.set(Extract(path, i.load() * Int(33), Int(33))),
                        
                        result.store(
                            If(GetByte(path_node.get(),Int(0)) == Int(1)).Then(
                                Sha256(Concat(result.load(), Extract(path_node.get(), Int(1), Int(32))))
                            ).Else(
                                Sha256(Concat(Extract(path_node.get(), Int(1), Int(32)), result.load()))
                            )
                        ),
                        
                        old_result.store(
                            If(GetByte(path_node.get(),Int(0)) == Int(1)).Then(
                                Sha256(Concat(old_result.load(), Extract(path_node.get(), Int(1), Int(32))))
                            ).Else(
                                Sha256(Concat(Extract(path_node.get(), Int(1), Int(32)), old_result.load()))
                            )
                        )
                    ),
                And(Eq(result.load(), new_root), 
                    Eq(old_result.load(),old_root),
                    Eq(Extract(Txn.note(),Int(0),Int(32)), new_root),
                    Eq(Extract(Txn.note(),Int(32),Int(32)), old_root))
            ])
