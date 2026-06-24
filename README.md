The first time the app is run it will give an error "cannot be opened because the developer cannot be verified" because I don't pay for Apple signature verification to be a registered public MacOS developer.

To get past that, right-click (or Control-click) the app → Open → Open again in the dialog. You only need to do that once; after that it launches normally every time.

The program doesn't do any actual changes to the system at all, it only runs checks to see if stuff is plugged in properly, and then provides instructions to the user on how to configure them properly once they're plugged in, or advice on troubleshooting if they're not plugged in properly.

When I came in the other day, I ran these commands in different scenarios, and saved the results to text files, and used those files to test and make sure the program can search the results of the commands for the right text, to accurately tell if stuff is plugged in properly.

The program runs these commands to check if stuff is plugged in and working, and then presents pop up messages for the user based on that:

To see if the USB adapter and the thunderbolt enclosure are plugged in:
`ioreg -p IOUSB -lw0`
To see if the VGA monitor is detected as a display, if it doesn't appear here, it still needs to be configured in that drop down widget in the top right for "Screen Mirroring":
`system_profiler SPDisplaysDataType`
To see if the BlackMagic drivers are installed and enabled:
`systemextensionsctl list`

Then it presents error messages with troubleshooting instructions and/or pictures to help configure the displays accordingly after verifying physical connectivity.
