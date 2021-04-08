import os, re
import traceback

QUIET_MODE = False

def _default_is_test_file(filepath):
    return filepath.endswith('.in')

def _default_in2out(infilepath):
    if filepath.endswith('.in'):
        infilepath = infilepath[:len('.in')]
    return infilepath + '.out'


def main(EXECUTE,
         testdir='tests/',
         is_test_file=_default_is_test_file, 
         in2out=_default_in2out,
         argv=[],
         failfirst=False,
         quiet_mode=False
        ):
    """ 
    
    Args:
        EXECUTE: str
            command to run to perform the test

            this can be customized by using any number of the following tags.
            (We will use the command 'java MyProgram' as an example)


            1) args:infilepath
            'java MyProgram {args:infilepath}`
            feeds the filepath of each test case as an argument:
            'java MyProgram mytestcase.in`


            2) pipe:infilepath
            'java MyProgram {pipe:infilepath}`
            pipes the filepath of each test case:
            'java MyProgram < mytestcase.in`


            3) args:infilepath:contents
            'java MyProgram {args:infilepath:contents}`
            feeds the contents of each test case filepath an argument:
            ```
            contents of the testcase
            ```
            'java MyProgram contents of the testcase`


            4) pipe:infilepath:contents
            'java MyProgram {args:infilepath:contents}`
            pipes the contents of each test case filepath:
            ```
            contents/is/usually/a/filepath
            ```
            'java MyProgram < contents/is/usually/a/filepath`


            5) args:infilepath:contents:foreach
            'java MyProgram {args:infilepath:contents:foreach}`
            feeds each line of the contents of each test case filepath as 
            an argument:
            ```
            contents
            of
            the
            testcase
            ```
            'java MyProgram contents`
            'java MyProgram of`
            'java MyProgram the`
            'java MyProgram testcase`

            its important to note that the output of each of these will be 
            compared to each line of the .out file

        TODO
    
    """
    global QUIET_MODE
    QUIET_MODE = quiet_mode

    # handle argv
    if argv[0].endswith('.py'):
        del argv[0]
    break_when_done = False
    while len(argv) >= 2:
        flag, val = argv[:2]
        del argv[:2]

        if flag == '-o':
            break_when_done = True
            if val.startswith('test='):
                val = val[len('test='):]
            if not os.path.exists(val):
                print(f"filapath '{val}' does no exist")
                return
            _overwrite_test(EXECUTE, val, in2out)
        # elif flag in ['-c', '--create']:
        #     break_when_done = True
        #     _create_mode()
    if break_when_done:
        return

    # collect all of the test filepaths
    tests = collect_tests(testdir, is_test_file)

    total = 0
    total_failed = 0
    # parse  execute command
    for testfilepath in tests:

        for outcome in _execute_test(EXECUTE, testfilepath, in2out):
            total += 1
            if type(outcome) == FailedTestException:
                print(outcome)
                
                # TODO: consider prinstack trace for any other Exception
                # check silence
                # traceback.print_exc()
                
                total_failed += 1

                if not quiet_mode:
                    print(outcome.overwrite_msg())

                if failfirst:
                    break

                continue
            else:
                if not quiet_mode:
                    print(f"{OK}PASSED{ENDC} {outcome}")

        if total_failed > 0 and failfirst:
            break

            if not quiet_mode:
                print(f"{OK}PASSED{ENDC} {testfilepath}")

    os.remove(f'{PRODUCED_OUT_FILE}')
    os.remove(f'{EXP_OUT_FILE}')
    if total_failed > 0:
        print(f"{FAIL}FAILED{ENDC} {total_failed}/{total} tests")
    else:
        print(f"{total}/{total} testcase{'' if total == 1 else 's'} {OK}PASSED{ENDC}")


def _execute_test(EXECUTE, infilepath, in2out):

    # check outfile existence
    outfilepath = in2out(infilepath)
    if not os.path.exists(outfilepath):
        yield FailedTestException(infilepath, 
            f"Could not find outputfile '{outfilepath}'")

    # construct command
    for command, expected_out in _generate_commands(EXECUTE, infilepath, outfilepath):

        # run program
        with open(PRODUCED_OUT_FILE, 'w') as temp_file:
            temp_file.write(os.popen(command).read())
        
        with open(EXP_OUT_FILE, 'w') as temp_file:
            temp_file.write(expected_out)
        
        # check difference between output
        diff = os.popen(f"diff {PRODUCED_OUT_FILE} {EXP_OUT_FILE}").read()

        if diff:
            failmsg = f'\nRUN:\n\t{command}'
            if ':infilepath:contents}' in EXECUTE:
                failmsg += f'INPUT:\n{_file_contents(infilepath)}\n'
            failmsg += f'\nOUTPUT:\n---\n{_file_contents(PRODUCED_OUT_FILE)}\n---'
            failmsg += f'\n\nEXPECTED:\n---\n{_file_contents(EXP_OUT_FILE)}\n---'
            print(diff)
            yield FailedTestException(infilepath, failmsg)
        else:
            yield command


def collect_tests(testdir, is_test_file):
    tests = []
    for root, dirs, files in os.walk(testdir):
        for file in files:
            joined = os.path.join(root, file)
            if is_test_file(joined):
                tests.append(joined)
    return tests


def _generate_commands(EXECUTE, infilepath, outfilepath):
    if '{args:infilepath:contents:foreach}' in EXECUTE:
        # open the infilepath
        incontents = _file_contents(infilepath).split('\n')
        outcontents = _file_contents(outfilepath).split('\n')

        ln = len(incontents)

        if ln != len(outcontents):
            raise FailedTestException(infilepath, 
                f"inputfile '{infilepath}' contains {ln} lines while "\
                f"outputfile '{outfilepath}' contains {len(outcontents)} lines"
            )

        for i in range(ln):
            inline, outline = incontents[i], outcontents[i] + '\n'
            # print(f"inline = |{inline}|")
            # print(f"outline = |{outline}|")

            if inline == '':
                return

            yield (
                EXECUTE.replace('{args:infilepath:contents:foreach}', inline), 
                outline
            )
    else:
        yield (
            _format_command(EXECUTE, infilepath), 
            _file_contents(outfilepath)
        )


def _format_command(EXECUTE, infilepath):
    if '{args:infilepath}' in EXECUTE:
        EXECUTE = EXECUTE.replace(
            '{args:infilepath}', 
            infilepath)

    if '{pipe:infilepath}' in EXECUTE:
        EXECUTE = EXECUTE.replace(
            '{pipe:infilepath}', 
            f'< {infilepath}')

    if '{args:infilepath:contents}' in EXECUTE:
        # collect contents
        infile_contents = _file_contents(infilepath)
        EXECUTE = EXECUTE.replace(
            '{args:infilepath:contents}', 
            infile_contents)

    if '{pipe:infilepath:contents}' in EXECUTE:
        infile_contents = _file_contents(infilepath)
        EXECUTE = EXECUTE.replace(
            '{pipe:infilepath:contents}', 
            f'< {infile_contents}')

    return EXECUTE

def _overwrite_test(EXECUTE, infilepath, in2out):
    outfilepath = in2out(infilepath)

    # construct command
    command = _format_command(EXECUTE, infilepath)

    # run program and write to out
    with open(outfilepath, 'w') as out_file:
        out_file.write(os.popen(command).read())

WHITE = '\033[37m'
OK = '\033[32m'
FAIL = '\033[31m'
ENDC = '\033[0m'
UNDERLINE = '\033[4m'

PRODUCED_OUT_FILE = 'temp_in'
EXP_OUT_FILE = 'temp_out'


class FailedTestException(Exception):
    def __init__(self, infilepath, msg, *args, **kwargs):
        self.infilepath = infilepath
        msg = f"{FAIL}FAILED{ENDC} {infilepath}:\n{msg}"
        super().__init__(msg, *args, **kwargs)
    def overwrite_msg(self):
        return f"To overwrite, run:\nmake overwrite test={self.infilepath}\n"


def _file_contents(filepath):
    with open(filepath) as f:
        return f.read()

def _create_mode():
    """
    Used to create new test cases

    tests are [in] and [out]
    so the user must specify 
    - the name of the [in] file (or default to lowest int)
    - the name of the [out] file (or default to prev name followed by .out)
    - contents of [in] file
    - contents of [out] file
    """
    pass

# TODO: ifmain