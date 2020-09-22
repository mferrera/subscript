import argparse
import logging
import dateutil

import xtgeo
import subscript

logger = subscript.getLogger(__name__)

DESCRIPTION = """Compare a 3D parameter at two different timestamps
in an Eclipse restart file, and write the difference pr. cell as
a 3D grid parameter in ROFF grid format.

The file extension ``.roff`` will be added to the OUTPUTNAME argument.
"""

CATEGORY = "utility.eclipse"

EXAMPLES = (
    "FORWARD_MODEL ECLDIFF2ROFF("
    "<ECLROOT>=<ECLBASE>, <PROP>=SGAS, "
    "<DIFFDATES>=diff_dates.txt"
    "<OUTPUT>=share/results/grids/eclgrid)"
)


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """Multiple inheritance used for argparse to get both defaults
    and raw description formatter"""

    # pylint: disable=unnecessary-pass
    pass


def get_parser():
    """Set up a parser for the command line utility"""
    parser = argparse.ArgumentParser(
        formatter_class=CustomFormatter, description=DESCRIPTION
    )

    parser.add_argument(
        "eclroot", type=str, help="Eclipse rootname. UNRST must lie alongside"
    )

    parser.add_argument(
        "prop", type=str, help="Property name to compute difference for, example SGAS"
    )

    parser.add_argument(
        "--diffdates",
        type=str,
        help=(
            "File containing a date pair pr line, in YYYYMMDD or YYYY-MM-DD format. "
            "Space-separated"
        ),
    )
    parser.add_argument(
        "--outputfilebase",
        type=str,
        default="eclgrid",
        help="Filename base for output files. Can contain a relative or absolute path.",
    )
    parser.add_argument(
        "--sep", default="--", type=str, help="Separator used to construct filenames"
    )

    parser.add_argument(
        "--datesep",
        default="_",
        type=str,
        help="Separator used in datepairs in output filenames",
    )
    parser.add_argument(
        "--datefmt", default="YYYYMMDD", type=str, help="Dateformat in output filenames"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose")
    return parser


def parse_diff_dates(filename):
    """Read a text file with one date pair pr. line, each date separated by space.

    The file can have dates in YYYYMMDD or in YYYY-MM-DD format, and
    the format can be mixed in the same file.

    Lines starting with "--" or "#" are ignored, so are empty lines.

    Example:
      20000101 20010101
      2003-01-01 2004-09-01

    Args:
        filename (str): Existing file

    Return:
        A list of date pairs as tuples. The tuples contain
            two strings, each string representing the date in YYYYMMDD
            format.
    """
    outputdateformat = "%Y%m%d"  # For xtgeo compatibility

    with open(filename, "r") as f_handle:
        lines = f_handle.readlines()

    lines = [line for line in lines if line.strip()]
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if not line.startswith("--")]
    lines = [line for line in lines if not line.startswith("#")]

    datelist = []
    for line in lines:
        line_components = line.split()
        if len(line_components) != 2:
            raise ValueError("Could not parse dateline {}".format(line))
        datelist.append(
            (
                dateutil.parser.parse(line_components[0]).strftime(outputdateformat),
                dateutil.parser.parse(line_components[1]).strftime(outputdateformat),
            )
        )
    return datelist


# pylint: disable=too-many-arguments
def ecldiff2roff_main(
    eclroot,
    prop,
    diffdates,
    outputfilebase="eclgrid",
    sep="--",
    datesep="_",
    datefmt="YYYYMMDD",
):
    """Main function for ecldiff2roff, taking positional and
    named arguments.

    Arguments correspond to argparse documentation
    """
    if not diffdates:
        logger.warning("No dates given. Nothing to do")
        return

    if isinstance(diffdates, str):
        diffdates = parse_diff_dates(diffdates)

    alldates = set()
    for date_pair in diffdates:
        alldates = alldates.union(set(date_pair))

    ecl_grid = xtgeo.grid3d.Grid().from_file(
        eclroot, fformat="eclipserun", restartprops=[prop], restartdates=alldates
    )
    logger.info("Loaded UNRST data at %s dates from %s", len(alldates), eclroot)

    supp_datefmts = {"YYYYMMDD": "%Y%m%d", "YYYY-MM-DD": "%Y-%m-%d"}
    if datefmt not in supp_datefmts:
        raise ValueError("Requested dateformat not supported {}".format(datefmt))

    for date_pair in diffdates:
        prop1 = ecl_grid.get_prop_by_name("{}_{}".format(prop, date_pair[0]))
        if prop1 is None or prop1.values is None:
            raise ValueError(
                "Could not extract {} at date {}".format(prop, date_pair[0])
            )

        prop2 = ecl_grid.get_prop_by_name("{}_{}".format(prop, date_pair[1]))
        if prop2 is None or prop2.values is None:
            raise ValueError(
                "Could not extract {} at date {}".format(prop, date_pair[1])
            )

        logger.info(
            "Computing difference for property %s between dates %s and %s",
            prop,
            str(date_pair[0]),
            str(date_pair[1]),
        )
        # Inplace substraction, prop1 = prop1 - prop2
        prop1.values -= prop2.values

        diffpropname = (
            prop.lower()
            + sep
            + dateutil.parser.parse(date_pair[0]).strftime(supp_datefmts[datefmt])
            + datesep
            + dateutil.parser.parse(date_pair[1]).strftime(supp_datefmts[datefmt])
        )
        filename = outputfilebase + sep + diffpropname + ".roff"

        logger.info("Writing to file %s", filename)
        prop1.to_file(filename, name=diffpropname)


def main():
    """Main function when called as a command line application.

    Will get arguments from command line, and wrap around ecldiff2roff_main().
    """
    parser = get_parser()
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)

    ecldiff2roff_main(
        eclroot=args.eclroot,
        prop=args.prop,
        diffdates=args.diffdates,
        outputfilebase=args.outputfilebase,
        sep=args.sep,
        datesep=args.datesep,
        datefmt=args.datefmt,
    )


if __name__ == "__main__":
    main()
