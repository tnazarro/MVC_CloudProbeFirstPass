# import tkinter as tk
# from tkinter import ttk, filedialog, messagebox
# import matplotlib
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
# from matplotlib.figure import Figure
# import seaborn as sns
# import matplotlib.dates as mdates

# #Imports the other modules in the same directory
# from controller import * #provides utility functions for common tasks
# from gui import * #The central hub that interfaces with the user
# from constants import * #Constants and global variables
# from plotting import * #functions that handle visualization
# from data_processing import * #functions that handle file loading and data frame manipulation
# from modern_calibration_window import * #handles the calibration window for the PAX data

def main():
    """
    Entry point for the application.
    Initializes the Tkinter root window and starts the main loop.
    """
    root = tk.Tk()  # Create the root window
    app = CloudProbeView(root)  # Instantiate the PAXView class
    app.mainloop()  # Start the Tkinter main loop

#If this file is run as a script, call the main function
if __name__ == "__main__":
    main()