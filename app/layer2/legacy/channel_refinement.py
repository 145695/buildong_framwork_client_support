from app.schemas.conversation import ConversationState, SourceChannel


def run_channel_refinement_agent(state: ConversationState) -> ConversationState:
    if state.source_channel == SourceChannel.EMAIL:
        state.trace.append("layer2:channel_refinement:email")
    elif state.source_channel == SourceChannel.VOICE:
        state.trace.append("layer2:channel_refinement:voice")
    else:
        state.trace.append("layer2:channel_refinement:chat")
    return state
