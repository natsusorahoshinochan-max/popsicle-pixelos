# SPDX-License-Identifier: Apache-2.0
# Read canonical kernel_to_cil output and emit only additive camera clone CIL.
# The caller must retain the complete original CIL, check this exit status, and
# verify the clone against the formally compiled camera policy before loading.
# No live policy is loaded here. Unexpected policy constructs fail closed.

function fail(message) {
    failed = 1
    print "camera policy clone: line " NR ": " message > "/dev/stderr"
    exit 1
}

# A lexer, not a general CIL rewriter. kernel_to_cil emits one complete form per
# line. Retain quoted filenames verbatim, including escaped quotes/parentheses.
function lex(line,    i, start, ch, depth, quoted, escaped) {
    for (i in token) delete token[i]
    for (i in begin) delete begin[i]
    for (i in finish) delete finish[i]
    count = 0
    depth = 0
    for (i = 1; i <= length(line);) {
        ch = substr(line, i, 1)
        if (ch ~ /[ \t\r]/) { i++; continue }
        start = i
        if (ch == "(" || ch == ")") {
            depth += (ch == "(" ? 1 : -1)
            if (depth < 0) fail("unbalanced canonical form")
            i++
        } else if (ch == "\"") {
            quoted = 1
            escaped = 0
            for (i++; i <= length(line); i++) {
                ch = substr(line, i, 1)
                if (!escaped && ch == "\"") { i++; quoted = 0; break }
                if (!escaped && ch == "\\") escaped = 1
                else escaped = 0
            }
            if (quoted) fail("unterminated filename")
        } else {
            while (i <= length(line) && substr(line, i, 1) !~ /[() \t\r]/) i++
        }
        token[++count] = substr(line, start, i - start)
        begin[count] = start
        finish[count] = i - 1
    }
    if (depth != 0) fail("multiline forms require a separate reviewed implementation")
    if (count && (token[1] != "(" || token[count] != ")")) fail("noncanonical form")
}

function replaced(line,    result, offset, i) {
    result = ""
    offset = 1
    for (i = 1; i <= count; i++) {
        if (!(token[i] in mapping)) continue
        result = result substr(line, offset, begin[i] - offset) mapping[token[i]]
        offset = finish[i] + 1
    }
    return result substr(line, offset)
}

BEGIN {
    mapping["priv_app_36"] = "popsicle_camera_app"
    mapping["priv_app_36_block_io_uring"] = "popsicle_camera_app_block_io_uring"
    mapping["priv_app_36_devpts"] = "popsicle_camera_app_devpts"
    mapping["priv_app_36_userfaultfd"] = "popsicle_camera_app_userfaultfd"
    mapping["priv_app_36_wrapfd"] = "popsicle_camera_app_wrapfd"
    inode["\"[io_uring]\""] = "priv_app_36_block_io_uring"
    inode["\"[userfaultfd]\""] = "priv_app_36_userfaultfd"
    inode["\"[wrapfd]\""] = "priv_app_36_wrapfd"
    allowed["allow"] = allowed["allowx"] = allowed["auditallow"] = 1
    allowed["auditallowx"] = allowed["dontaudit"] = allowed["dontauditx"] = 1
    allowed["typetransition"] = allowed["typechange"] = allowed["typemember"] = 1
    allowed["roletype"] = 1
}

{
    if ($0 ~ /^[ \t\r]*$/) next
    lex($0)
    relevant = 0
    for (i = 1; i <= count; i++) {
        if (token[i] ~ /^popsicle_camera_app($|_)/) fail("destination namespace already exists")
        if (token[i] ~ /^priv_app_36($|_)/ && !(token[i] in mapping)) {
            fail("unexpected source namespace member " token[i])
        }
        if (token[i] in mapping) relevant = 1
    }
    if (!relevant) next
    kind = token[2]
    if (kind == "type") {
        if (count != 4 || !(token[3] in mapping)) fail("unexpected type declaration")
        if (declared[token[3]]++) fail("duplicate source type declaration")
        delta[++delta_count] = replaced($0)
    } else if (kind == "typeattributeset") {
        if (count < 7 || token[4] != "(" || token[count - 1] != ")") {
            fail("noncanonical attribute membership")
        }
        members = ""
        for (i = 5; i < count - 1; i++) {
            if (token[i] !~ /^[A-Za-z0-9_.-]+$/) fail("attribute expression is not a flat type set")
            if (token[i] == "and" || token[i] == "or" || token[i] == "not" || token[i] == "all") {
                fail("attribute expression is not a concrete type set")
            }
            if (token[i] in mapping) members = members " " mapping[token[i]]
        }
        if (members == "" || token[3] in mapping) fail("unexpected attribute reference")
        delta[++delta_count] = "(typeattributeset " token[3] " (" substr(members, 2) "))"
    } else if (kind in allowed) {
        delta[++delta_count] = replaced($0)
        if (kind == "allowx" && token[5] == "(" && token[6] == "nlmsg") nlmsg_count++
        if (kind == "typetransition" && token[5] == "anon_inode") {
            if (count != 8 || token[3] != "priv_app_36" || token[4] != "priv_app_36" \
                    || !(token[6] in inode) || token[7] != inode[token[6]]) {
                fail("unexpected private anonymous-inode transition")
            }
            if (named[token[6]]++) fail("duplicate private anonymous-inode transition")
            named_count++
        }
    } else {
        # In particular, copying a constraint as a second global constraint is
        # not a valid clone. Attribute-based constraints inherit added members.
        fail("unsupported source namespace construct " kind)
    }
}

END {
    if (failed) exit 1
    for (name in mapping) {
        if (declared[name] != 1) fail("missing source type " name)
    }
    if (named_count != 3 || nlmsg_count < 1) fail("incomplete named-inode or nlmsg baseline")
    for (i = 1; i <= delta_count; i++) print delta[i]
    print "camera policy clone: " delta_count " additive forms; 5 types; " \
        named_count " named inode transitions; " nlmsg_count " nlmsg rules" > "/dev/stderr"
}
