import sys
import os
sys.path.append(os.getcwd())
import asyncio
from app.services.prompt_builder import build_prompt, PromptContext

async def test_difficulty_prompts():
    print("Testing difficulty levels in prompt construction...\n")
    
    levels = [1, 5, 10]
    
    for level in levels:
        context = PromptContext(
            frequency_group="tower",
            airport="MRPV",
            difficulty=level
        )
        
        bundle = build_prompt(
            intent="request_takeoff",
            context=context,
            transcript="Torre, Tango Alpha Bravo listo para despegue",
            scenario={},
            phase={},
            turn_history=[]
        )
        
        print(f"--- Difficulty Level {level} ---")
        if "Modo relajado" in bundle.system_prompt:
            print("Found 'Modo relajado' instruction (Correct for low difficulty)")
import sys
import os
sys.path.append(os.getcwd())
import asyncio
from app.services.prompt_builder import build_prompt, PromptContext

async def test_difficulty_prompts():
    print("Testing difficulty levels in prompt construction...\n")
    
    levels = [1, 5, 10]
    
    for level in levels:
        context = PromptContext(
            frequency_group="tower",
            airport="MRPV",
            difficulty=level
        )
        
        bundle = build_prompt(
            intent="request_takeoff",
            context=context,
            transcript="Torre, Tango Alpha Bravo listo para despegue",
            scenario={},
            phase={},
            turn_history=[]
        )
        
        print(f"--- Difficulty Level {level} ---")
        if "Modo relajado" in bundle.system_prompt:
            print("Found 'Modo relajado' instruction (Correct for low difficulty)")
        elif "Modo normal" in bundle.system_prompt:
            print("Found 'Modo normal' instruction (Correct for medium difficulty)")
        elif "Modo estricto" in bundle.system_prompt:
            print("Found 'Modo estricto' instruction (Correct for high difficulty)")
        else:
            print("ERROR: No difficulty instruction found!")
            
        print(f"Snippet: {bundle.system_prompt[200:400]}...\n")

    # Test default difficulty
    print("--- Default Difficulty Test ---")
    context_default = PromptContext(
        frequency_group="tower",
        airport="MRPV"
        # No difficulty specified, should default to 5
    )
    bundle_default = build_prompt(
        intent="request_takeoff",
        context=context_default,
        transcript="Torre, Tango Alpha Bravo listo para despegue",
        scenario={},
        phase={},
        turn_history=[]
    )
    
    if "Modo normal" in bundle_default.system_prompt:
        print("SUCCESS: Default difficulty resulted in 'Modo normal' (Level 5)")
    else:
        print("FAILURE: Default difficulty did NOT result in 'Modo normal'")
        print(f"Snippet: {bundle_default.system_prompt[200:400]}...")

if __name__ == "__main__":
    asyncio.run(test_difficulty_prompts())
