"""Minimal spawn-safe entry point; speech children do not import the Qt UI."""
if __name__ == '__main__':
    import sys
    from app import main
    sys.exit(main())
