"""Parse numbered questions and conservative, reviewable choice instructions."""
import re
from backend.models import QuestionItem, QuestionPaper, ChoiceGroup

NUMBERS = dict(zip('one two three four five six seven eight nine ten'.split(), range(1, 11)))
QUESTION = re.compile(r'^(?:q(?:uestion)?[\s.]*)?(\d{1,3}(?:\([a-z0-9]+\)|[a-z])?)[.:)\s-]+(.*)', re.I)
MARKS = re.compile(r'[\[({]\s*(\d+(?:\.\d+)?)\s*(?:marks?|m)?\s*[\])}]|\b(\d+(?:\.\d+)?)\s*marks?\b', re.I)


def parse_paper(text):
    questions, groups, warnings, section_rules = [], [], [], {}
    section, current, pending_or, or_pairs = 'General Section', None, False, []
    title, code = 'Draft Examination Question Paper', 'SUB101'
    explicit_marks = set()

    def flush():
        nonlocal current
        if current:
            if not current['question_text'].strip():
                warnings.append(f"{current['question_id']}: no question text was extracted; replace the placeholder.")
                current['question_text'] = '[No question text extracted - replace before auditing]'
            questions.append(QuestionItem(**current))
            current = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^(section|part)\s+[A-Z0-9]\b', line, re.I):
            flush()
            section = line.strip(' :-')
            if pending_or:
                warnings.append('An OR crossed a section boundary; configure the choice group manually.')
                pending_or = False
        instruction = re.search(r'\b(?:attempt|answer)\s+any\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', line, re.I)
        if instruction:
            value = instruction.group(1).lower()
            section_rules[section] = int(value) if value.isdigit() else NUMBERS[value]
            continue
        if re.match(r'^(section|part)\s+[A-Z0-9]\b', line, re.I):
            continue
        if line.upper().strip('()[] ') == 'OR':
            flush()
            pending_or = True
            continue
        match = QUESTION.match(line)
        if match:
            flush()
            qid = 'Q' + match.group(1).upper()
            existing = {q.question_id for q in questions}
            original, suffix = qid, 2
            while qid in existing:
                qid = f'{original}_ALT{suffix}'
                suffix += 1
            if pending_or and questions:
                or_pairs.append((questions[-1].question_id, qid))
            elif pending_or:
                warnings.append('OR has no preceding question; correct choice groups before auditing.')
            pending_or = False
            body = match.group(2)
            marks_match = MARKS.search(body)
            if marks_match:
                marks = float(marks_match.group(1) or marks_match.group(2))
                explicit_marks.add(qid)
            else:
                marks = 2.0 if 'part a' in section.lower() else 10.0
            current = dict(question_id=qid, section=section, question_text=MARKS.sub('', body).strip(), marks=marks)
        elif current:
            marks_match = MARKS.search(line)
            if marks_match and current['question_id'] not in explicit_marks:
                current['marks'] = float(marks_match.group(1) or marks_match.group(2))
                explicit_marks.add(current['question_id'])
            current['question_text'] += ' ' + MARKS.sub('', line).strip()
        else:
            if re.search(r'exam|test', line, re.I):
                title = line
            code_match = re.search(r'\b([A-Z]{2,4}\s?\d{3,4})\b', line)
            if code_match:
                code = code_match.group(1).replace(' ', '')
    flush()
    if pending_or:
        warnings.append('Trailing OR has no alternative; correct it before auditing.')
    for q in questions:
        if q.question_id not in explicit_marks:
            warnings.append(f'{q.question_id}: marks were inferred; verify {q.marks:g} marks.')
    # Merge chains Q1 OR Q2 OR Q3 into one choose-one group.
    chains = []
    for left, right in or_pairs:
        chain = next((c for c in chains if left in c), None)
        if chain is None:
            chains.append([left, right])
        else:
            chain.append(right)
    used = set()
    for chain in chains:
        groups.append(ChoiceGroup(group_id=f'OR{len(groups)+1}', question_ids=chain, choose=1))
        used.update(chain)
    for name, choose in section_rules.items():
        members = [q.question_id for q in questions if q.section == name]
        if set(members) & used:
            warnings.append(f'{name}: nested OR/attempt-any rules need manual correction; only OR groups were retained.')
        elif 0 < choose < len(members):
            groups.append(ChoiceGroup(group_id=f'ANY{len(groups)+1}', question_ids=members, choose=choose))
        else:
            warnings.append(f'{name}: attempt-any count {choose} does not define a valid choice; check the questions.')
    if not questions:
        warnings.append('No numbered questions found. Add questions in the preview before auditing.')
    return QuestionPaper(paper_title=title, course_code=code, total_marks=sum(q.marks for q in questions),
                         questions=questions, choice_groups=groups, parsing_warnings=warnings)
