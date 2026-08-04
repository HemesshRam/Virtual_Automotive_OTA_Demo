from ecus.base.state_machine import StateMachine, ECUState


sm = StateMachine()

print(sm.current_state.name)

sm.set_state(ECUState.READY)

print(sm.current_state.name)

sm.set_state(ECUState.DISCOVERED)

print(sm.current_state.name)
