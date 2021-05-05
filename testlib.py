import os, re
import subprocess
import traceback
from pathlib import Path
import fnmatch

QUIET_MODE = False



"""
def _validate_stderr_func():
    def f(infilepath, stdout='', stderr=''):
        return _default_validate_output(infilepath, stdout='', stderr='', stream='stderr'):
    return f
"""

def _infilepath2outfilepath(infilepath):
    # get the test case for this input file
    outfilepath = infilepath
    if outfilepath.endswith('.in'):
        outfilepath = outfilepath[:len('.in')]
    outfilepath += '.out'

    return outfilepath

class OutputValidators:
    """
    default args to OutputValidators:
        infilpath
    default kwargs to OutputValidators:
        stdout
        stderr
    """
    def diff(infilepath, stdout='', stderr='', **kwargs):
        """ checks difference between  """

        # check for stream
        stream = kwargs.get('stream')
        if stream == None:
            stream = 'stdout'

        # compare their outputs
        with open(PRODUCED_OUT_FILE, 'w') as temp_file:
            if stream == 'stdout':
                temp_file.write(stdout)
            else:
                temp_file.write(stderr)
        
        # get the test case for this input file
        outfilepath = _infilepath2outfilepath(infilepath)
        # now collect the output contents
        expected_out = file_contents(outfilepath)
        # write contents to file
        with open(EXP_OUT_FILE, 'w') as temp_file:
            temp_file.write(expected_out)
        
        # check difference between output
        diff = os.popen(f"diff {PRODUCED_OUT_FILE} {EXP_OUT_FILE}").read()

        # if there is no difference, we passed
        if not diff:
            return '', True

        # else, generate error message
        failmsg = f'\nRUN:\n\t{kwargs.get("command")}'
        if ':infilepath:contents}' in EXECUTE:
            failmsg += f'INPUT:\n{file_contents(infilepath)}\n'
        failmsg += f'\nOUTPUT:\n---\n{file_contents(PRODUCED_OUT_FILE)}\n---'
        failmsg += f'\n\nEXPECTED:\n---\n{file_contents(EXP_OUT_FILE)}\n---'
        return failmsg, False
        


def _execute_test(EXECUTE, infilepath, validate_output):

    # construct command
    for command in _generate_commands(EXECUTE, infilepath):

        # run program
        proc = subprocess.Popen(command.split(), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
        ) 
        stdout, stderr = proc.communicate() 
        stream2output = {
            'stdout': stdout.decode('utf-8'), 
            'stderr': stderr.decode('utf-8')
        }

        msg, passed = validate_output(infilepath, command=command, **stream2output)
        if passed:
            yield command
        else:
            yield FailedTestException(infilepath, msg)


def _generate_commands(EXECUTE, infilepath):
    """
    For now we will deprecate the foreach feature until further notice
    """
    yield _format_command(EXECUTE, infilepath)


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
        infile_contents = file_contents(infilepath)
        EXECUTE = EXECUTE.replace(
            '{args:infilepath:contents}', 
            infile_contents)

    if '{pipe:infilepath:contents}' in EXECUTE:
        infile_contents = file_contents(infilepath)
        EXECUTE = EXECUTE.replace(
            '{pipe:infilepath:contents}', 
            f'< {infile_contents}')

    return EXECUTE

def _overwrite_test(EXECUTE, infilepath):
    outfilepath = _infilepath2outfilepath(infilepath)

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
        return f"To overwrite, run:\npython3 test.py overwrite {self.infilepath}\n"


def file_contents(filepath):
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






def main(EXECUTE,
         test_regex='tests/*.in',
         validate_output=OutputValidators.diff,
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
    if break_when_done:
        return

    # collect tests from regex
    tests = map(
        str, 
        filter(
            lambda x: fnmatch.fnmatch(str(x), test_regex), 
            Path('.').rglob('*')
        )
    )

    total = 0
    total_failed = 0
    # parse  execute command
    for testfilepath in tests:

        for outcome in _execute_test(EXECUTE, testfilepath, validate_output):
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

    if os.path.isfile(PRODUCED_OUT_FILE):
        os.remove(PRODUCED_OUT_FILE)
    if os.path.isfile(EXP_OUT_FILE):
        os.remove(EXP_OUT_FILE)
    if total_failed > 0:
        print(f"{FAIL}FAILED{ENDC} {total_failed}/{total} tests")
    else:
        print(f"{total}/{total} testcase{'' if total == 1 else 's'} {OK}PASSED{ENDC}")
