"""All prompt templates for GrantSmith.

Edit the text here to change how drafts are written. Nothing else in the
codebase contains prompt language.
"""

SYSTEM_PROMPT = """\
You are an experienced grant writer drafting a funding proposal on behalf of \
a nonprofit organization. You write in the organization's own voice: warm, \
direct, concrete, and confident without being boastful.

Rules:
- Use only facts provided in the organization facts. Never invent statistics, \
program names, dollar amounts, dates, or outcomes.
- If the facts provided do not cover something the question asks about, write \
around the gap gracefully or insert a bracketed note like [ADD DETAIL] for \
the human editor.
- Match the tone and style of the example past proposals.
- When sponsor context is provided, tailor the emphasis of your answer to \
align the organization's mission and programs with that sponsor's stated \
priorities, values, and focus areas, and draw those connections where they \
are genuine. Never invent facts about the sponsor, and never claim a \
relationship or shared history that is not present in the sponsor context.
- Write polished prose paragraphs. Do not use markdown formatting, headings, \
or bullet points in your answer.
- Do not restate the question in your answer.
"""

USER_PROMPT = """\
Below are the organization's facts, followed by excerpts from past proposals \
that show the organization's writing style,{sponsor_intro} followed by one \
question from a funder's grant application.

<organization_facts>
{org_facts}
</organization_facts>

<past_proposals>
{examples}
</past_proposals>
{sponsor_block}
<question>
{question}
</question>

Write a polished proposal section that answers this one question in the \
organization's voice.{sponsor_instruction} Respond with the section text only.
"""

SPONSOR_BLOCK = """
<sponsor_context>
{sponsor_context}
</sponsor_context>
"""


def build_user_prompt(
    org_facts: str,
    examples: str,
    question: str,
    sponsor_context: str = "",
) -> str:
    """Fill the user prompt template for a single question.

    When sponsor_context is provided, a sponsor block and tailoring
    instruction are woven in. When it is empty, the prompt reads exactly as it
    did without any sponsor.
    """
    has_sponsor = bool(sponsor_context and sponsor_context.strip())
    return USER_PROMPT.format(
        org_facts=org_facts.strip(),
        examples=examples.strip(),
        question=question.strip(),
        sponsor_intro=(
            " followed by context about the sponsor this grant is aimed at,"
            if has_sponsor
            else ""
        ),
        sponsor_block=(
            SPONSOR_BLOCK.format(sponsor_context=sponsor_context.strip())
            if has_sponsor
            else ""
        ),
        sponsor_instruction=(
            " Tailor the emphasis to align with the sponsor's priorities "
            "without inventing any facts about the sponsor."
            if has_sponsor
            else ""
        ),
    )
