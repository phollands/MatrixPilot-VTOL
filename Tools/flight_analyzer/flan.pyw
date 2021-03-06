#  This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

#  Author: Peter Hollands, Copyright Peter Hollands 2009, 2010, 2011 
#
#  The following 3 lines require keyword insertion to be turned on
#  in the code.google.com subversion repository. 
#  $Rev:: 270           $:  Revision of last commit
#  $Author:: peter.holl#$:  Author of last commit
#  $Date:: 2010-01-31 2#$:  Date of last commit

from xml.dom import minidom
from math  import *
from Tkinter import *
from tkMessageBox import *
from zipfile import ZipFile,ZIP_DEFLATED
from time import sleep
from time import time
import tkFileDialog
import datetime
import subprocess
import pickle
import re
import sys
import os
import stat

from matrixpilot_lib import telemetry


def walktree (top = ".", depthfirst = True):
    names = os.listdir(top)
    if not depthfirst:
        yield top, names
    for name in names:
        try:
            st = os.lstat(os.path.join(top, name))
        except os.error:
            continue
        if stat.S_ISDIR(st.st_mode):
            for (newtop, children) in walktree (os.path.join(top, name), depthfirst):
                yield newtop, children
    if depthfirst:
        yield top, names



class colors :
    def __init__(self) :
        # The following web safe colors taken from
        # http://en.wikipedia.org/wiki/Web_colors
        self.aqua    = "aqua",   "00FFFF"
        self.grey    = "grey",   "808080"
        self.navy    = "navy",   "000080"
        self.silver  = "silver", "C0C0C0"
        self.green   = "green",  "008000"
        self.olive   = "olive",  "808000"
        self.teal    = "teal",   "008080"
        self.blue    = "blue",   "0000FF"
        self.lime    = "lime",   "00FF00"
        self.purple  = "purple", "800080"
        self.white   = "white",  "FFFFFF"
        self.fuchsia = "fuchsia","FF00FF"
        self.maroon  = "maroon", "800000"
        self.red     = "red",    "FF0000"
        self.yellow  = "yellow", "FFFF00"
        self.black   = "black",  "000000"
        self.list = \
            [self.aqua,self.blue,self.fuchsia,self.grey,\
             self.green,self.lime,self.maroon,self.navy,self.olive,self.purple,\
             self.teal, self.yellow]
        self.list2 = \
            [self.aqua,self.blue,self.fuchsia,self.grey,\
             self.green,self.lime,self.maroon,self.navy,self.olive,self.purple,\
             self.teal, self.yellow, self.red]
        
def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"
    
def C_pre_processor(C_source_filename):
    """"Use the C Pre Processor to parse a C source code file like waypoints.h"""
    try:
        programfiles = os.environ['ProgramFiles']
    except:
        #No luck with Windows environment variable, what about GCC?
        try:
            output = subprocess.Popen(["/bin/sh", "-c", "gcc -E " + shellquote(C_source_filename)],
                                   stdout=subprocess.PIPE, universal_newlines=True).communicate()[0]
        except:
            print "No GCC found either."
            error_message = "Cannot find a C preprocessor (GCC) \n" + \
                "This is needed for processing wayoint files \n" + \
                "Currently the location is hardcoded in flan.py." 
            print error_message
            showerror(title="Error: No C Pre-Processor Available",
                message = error_message)
            sys.exit()
    else:
        C_pre_processor_executable1 = \
             os.path.join(programfiles,'Microchip\\MPLAB C30\\bin\\bin\\pic30-coff-cpp.exe')
        C_pre_processor_executable2 = \
                os.path.join(programfiles,'Microchip\\mplabc30\\v3.25\\bin\\bin\\pic30-coff-cpp.exe')
        # Check that the exectuable exists ....
        if os.path.exists(C_pre_processor_executable1):
            output = subprocess.Popen([C_pre_processor_executable1,C_source_filename],
                                     stdout=subprocess.PIPE).communicate()[0]
        elif os.path.exists(C_pre_processor_executable2):
            output = subprocess.Popen([C_pre_processor_executable2,C_source_filename],
                                     stdout=subprocess.PIPE).communicate()[0]
        else :
            error_message = "Cannot find the following important executable file:\n" + \
                    C_pre_processor_executable2 + "\n" + \
                    "This is needed for processing wayoint files \n" + \
                    "Currently the location is hardcoded in flan.py." 
            print error_message
            showerror(title="Error: No C Pre-Processor Available",
                    message = error_message)
            sys.exit()
    if debug: print "Ouput from C Pre Processor Follows: \n", output
    return(output)

def convert_meters_north_to_lat(meters):
    """Converts relative meters North to Latittude  times 10 to the power 7
    (which is the native scale of lattitude returned from an EM606A GPS)"""
    return(90 * meters)

def convert_meters_east_to_lon(meters,lat):
    """Converts relative meters East to Longitude times 10 to the power 7"""
    return((90 * meters)/ (cos(((lat / 10000000.0) / 360)*2*pi)))

def get_fixed_origin_coords(text):
    """Parse s waypoints.h file to find absolute coordinatates of the origin"""
    
    pattern = r"""
                                 ## 
    (^\#[Dd]efine)               ## group(1)
    [\s]*                        ## White Space
    (FIXED_ORIGIN_LOCATION)      ## group(2)
    [\s]*{[\s]*                  ## White Space and Curly bracket delimeter
    ([-]*[0-9]+)                 ## group(3) Longitude * 10 ** 7
    [\s]*,[\s]*                  ##
    ([-]*[0-9]+)                 ## group(4) Latitude * 10 ** 7
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    m = regex.finditer(text)
    return m

def get_fixed_origin(text):
    """Parse a waypoints.h file to see if it is using a fixed origin"""
    
    pattern = r"""
                        ## 
    (^\#[Dd]efine)      ## group(1)
    [\s]*               ## White Space
    (USE_FIXED_ORIGIN)  ## group(2)
    [\s]*               ## White Space
    ([0-9]+)            ## group(3) Should be "1" if using Fixed Origin
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    m = regex.finditer(text)
    return m

def get_waypoints_with_defines(text):
    """Return a list of waypoints with alhanumeric values for waypoint values"""
    pattern = r"""
                            ## Regular Expressions for parsing waypoints.h
    ^[\s]*{[\s]*{[\s]*      ## Find the start of a line including "{" "{" and space
    ([-]*[\s]*[a-zA-Z0-9]+) ## Group 1: Waypoint Relative East in meters or Lon 
    [\s]*,[\s]*             ## white space then a "," the white space
    ([-]*[\s]*[a-zA-Z0-9]+) ## Group 2: Waypoint Relative North in meters or Lat
    [\s]*,[\s]*             ##
    ([-]*[\s]*[a-zA-Z0-9]+) ## Group 3:Waypoint Atitlude relative to origin in meters
    [\s]*}[\s]*,[\s]*       ## close out waypoints "}"
    ([^}]+)                 ## Group 4: Waypoint options like F_NORMAL
    }[\s]*,                 ##
    ([^\n]*\n)              ## Group 5: Everything up to the end of the line, Comments
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    m = regex.finditer(text)
    return m
    

def get_waypoints(text):
    """retrieve a list of waypoints pattern matches.
    Routine should be applied to a waypoints.h with /* type comments removed
    Note that this routine will only cope with Numeric values for waypoints.
    SO do not use if the values  are reprsented with #defines. e.g. run the
    C preprocessor over the file first, before presenting to this routine"""
    pattern = r"""
                        ## Regular Expressions for parsing waypoints.h
    ^[\s]*{[\s]*{[\s]* ## Find the start of a line including "{" "{" and space
    #[\s]*{[\s]*{[\s]*   ## Find "{" "{" and space
    ([-]*[\s]*[0-9]+)   ## Group 1: Waypoint Relative East in meters or Lon 
    [\s]*,[\s]*         ## white space then a "," the white space
    ([-]*[\s]*[0-9]+)   ## Group 2: Waypoint Relative North in meters or Lat
    [\s]*,[\s]*         ##
    ([-]*[\s]*[0-9]+)   ## Group 3:Waypoint Atitlude relative to origin in meters
    [\s]*}[\s]*,[\s]*   ## close out waypoints "}"
    ([^}]+)             ## Group 4: Waypoint options like F_NORMAL
    ([^\n]*\n)          ## Group 5: Everything up to the end of the line, Comments
    """
    #regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    regex = re.compile(pattern, re.VERBOSE|re.DOTALL)
    #m = regex.finditer(text)

    # Code here modified to take account of multiple different waypoints lists
    # There are now normal waypoints and RTL waypoints
    # We are on the edge of what can be achieved without proper parsing routines for C
    NOT_SET = 0
    NORMAL_WAYPOINT = 1
    RTL_WAYPOINT = 2
    pattern2 = ".*\n"
    regex2 = re.compile(pattern2)
    m2 = regex2.finditer(text)
    pattern3 = ".*waypoints\[\].*"
    regex3 = re.compile(pattern3)
    pattern4 = ".*rtlWaypoints\[\].*"
    regex4 = re.compile(pattern4)
    waypoint_type  = NOT_SET
    waypoints_list  = [] # an empty list of lists, initially
    for line in m2 : 
        m3  = regex3.match(line.group(0))
        if m3 :
            waypoint_type = NORMAL_WAYPOINT
        m4 = regex4.match(line.group(0))
        if m4:
            waypoint_type = RTL_WAYPOINT
        m = regex.match(line.group(0))
        if m:
            try:
                waypoint_with_type = [m, waypoint_type ]
                waypoints_list.append(waypoint_with_type)
            except:
                print"Error in get_waypoints function when matching waypoints from waypoints.h"
    return waypoints_list

def remove_slash_comments(text):
    """ remove blank newlines and single line comments of the form //"""

    pattern = r"""
           ([^\n]*\n)
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    noncomments = [m.group(0) for m in regex.finditer(text) if m.group(0)]
    text_to_parse = ""
    for line in noncomments:
        f = re.match("//", line)
        if not f :
            text_to_parse = text_to_parse + line
    return text_to_parse
            
def remove_comments(text):
    """ remove c-style comments.
        text: blob of text with comments (can include newlines)
        returns: text with comments removed
    """
    pattern = r"""
                            ##  --------- COMMENT ---------
           /\*              ##  Start of /* ... */ comment
           [^*]*\*+         ##  Non-* followed by 1-or-more *'s
           (                ##
             [^/*][^*]*\*+  ##
           )*               ##  0-or-more things which don't start with /
                            ##    but do end with '*'
           /                ##  End of /* ... */ comment
         |                  ##  -OR-  various things which aren't comments:
           (                ## 
                            ##  ------ " ... " STRING ------
             "              ##  Start of " ... " string
             (              ##
               \\.          ##  Escaped char
             |              ##  -OR-
               [^"\\]       ##  Non "\ characters
             )*             ##
             "              ##  End of " ... " string
           |                ##  -OR-
                            ##
                            ##  ------ ' ... ' STRING ------
             '              ##  Start of ' ... ' string
             (              ##
               \\.          ##  Escaped char
             |              ##  -OR-
               [^'\\]       ##  Non '\ characters
             )*             ##
             '              ##  End of ' ... ' string
           |                ##  -OR-
                            ##
                            ##  ------ ANYTHING ELSE -------
             .              ##  Anything other char
             [^/"'\\]*      ##  Chars which doesn't start a comment, string
           )                ##    or escape
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    noncomments = [m.group(2) for m in regex.finditer(text) if m.group(2)]

    return "".join(noncomments)


def process_CAM_VIEW_LAUNCH(text):
    """Do the job of the C pre-processor for the #define for CAM_VIEW_LAUNCH
       as we do not know where to point the C-preprocessor to find defines.h
       which is where CAM_VIEW_LAUNCH is defined."""

    pattern = r"""
           CAM_VIEW_LAUNCH
    """
    regex = re.compile(pattern, re.VERBOSE|re.MULTILINE|re.DOTALL)
    expanded_text = regex.sub("{ 0 , 0, 0 }",text)
    return expanded_text

def waypoints_do_not_need_telemetry(waypoint_file) :
    """Check to see whether the origin file is using a movable origin AND has
    some relative waypoints in it. if so, return False.
    Return True if using a fixed origin OR all
    the file has all absolute waypoints and no relative waypoints"""
    code_w_comments = open(waypoint_file).read()
    code_wo_star_comments = remove_comments(code_w_comments)
    code_wo_comments = remove_slash_comments(code_wo_star_comments)
    origin_line = get_fixed_origin(code_wo_comments)
    for y in origin_line :
        if debug: print y.group(1), y.group(2), y.group(3)
        if (int(y.group(3)) == 1):  # We are using an absolute and specified origin
            if debug: print waypoint_file,"\n uses a fixed fixed origin"
            return True
        else :
            #check to see if we have any relative waypoints...
            waypoints_list = get_waypoints_with_defines(code_wo_comments)
            
            for waypoint in waypoints_list :
                if debug: print "here is a waypoint line to analyse" , waypoint.group(4)
                match = re.match(".*F_ABSOLUTE.*",waypoint.group(4)) #
                if match:
                    if debug: print "Waypoint is Absolute"
                else:
                    if debug: print "did not find an F_ABSOLUTE this time so file has RELATIVE waypoints"
                    if debug: print waypoint_file, "uses a movable (boot up time) origin for relative coordinates"
                    return False
            if debug:
                if debug: print "waypoint file uses a movable origin \nbut there are no relative waypoints\n" 
            showinfo(title = "oops", message = "paused for test purposes")
            return True
    ## this routine should never get to this point. 
    showinfo(title = "Problems analyzing waypoints.h file",
             message = "flan.py was not able to \n determine whether waypoints.h uses \n a " +
             "fixed origin or a movable origin and so is exiting.")
    sys.exit()

def get_waypoints_list_in_absolute_lat_long(waypoint_file,flight_origin):
    """ Convert waypoint file with absolute and relative coordinates to all absolute"""
    WAYPOINT_TYPE = 1
    code_w_comments = open(waypoint_file).read() # Code with comments
    code_wo_star_comments = remove_comments(code_w_comments) # Code without star comments
    code_wo_comments = remove_slash_comments(code_wo_star_comments) # Code without comments
    origin_line = get_fixed_origin(code_wo_comments)
    #### Setup the Origin for use by Relative Coordinates ####
    for y in origin_line :
        if debug: print y.group(1), y.group(2), y.group(3)
        if (int(y.group(3)) == 1):  # We are using an absolute and specified origin
            if debug: print "This file uses a fixed pre-defined origin for relative coordinates"
            fixed_origin_line = get_fixed_origin_coords(code_wo_comments)
            for z in fixed_origin_line :
                origin_east = int(z.group(3))
                origin_north = int(z.group(4))
                if debug: print "origin east is ", origin_east
                if debug: print "origin north is", origin_north
        elif (int(y.group(3)) == 0) :# We are using the boot up spot as the origin
            #print "Using plane's boot up location as origin"
            origin_east = flight_origin.longitude
            origin_north = flight_origin.latitude
            #print "Origin: Lon: ",origin_east,"Lat: ",origin_north
        else :
            if debug: print "Error in deciding what origin to use", y.group(3)
    #### Get the Actual Waypoint List, convert relative waypoints to absolute ###
    C_pre_processed_code = C_pre_processor(waypoint_file)    
    waypoints_list = get_waypoints(C_pre_processed_code)
    waypoints_geo = ([],[],[]) # An empty list of waypoints in degrees for Lat & Lon, and meters for Alt (three lists of waypoint lists)
    if debug:
        print "*** Iterating through waypoints list:"
    for m in waypoints_list :
        if debug:
            print "found one: " + m[0].group(0)
        match = re.match(".*F_ABSOLUTE.*",m[0].group(4)) # 
        if match:
            this_waypoint = (int(m[0].group(1)),int( m[0].group(2)),(int(m[0].group(3)) + (flight_origin.altitude/100)),m[0].group(5))
            
        else :
            lat = convert_meters_north_to_lat(int(m[0].group(2)))    + origin_north
            lon = convert_meters_east_to_lon(int(m[0].group(1)),lat) + origin_east
            this_waypoint = [lon, lat,(int(m[0].group(3)) + (flight_origin.altitude/100)), m[0].group(0)]
        waypoints_geo[m[WAYPOINT_TYPE]].append(this_waypoint)
    
    return (waypoints_geo)

def generate_waypoints_kml(waypoints_geo,filename):
    LAT = 1
    LON = 0
    ALT = 2
    COMMENT = 3
    
    NORMAL_WAYPOINT = 1
    RTL_WAYPOINT = 2
    
    for waypoint_type in 1, 2 :
        index = 0
        for waypoint in waypoints_geo[waypoint_type]:
            print >> filename, """   <Placemark> 
          <name>""",
            if waypoint_type == NORMAL_WAYPOINT:
                print >> filename, "W",index,"""</name>""",
            elif waypoint_type == RTL_WAYPOINT:
                print >> filename, "R",index,"""</name>""",
            else :
                print >> filename, "?",index,"""</name>"""
            print >> filename, """<description>""",
            print >> filename, waypoints_geo[waypoint_type][index][COMMENT],
            print >> filename, """</description>
           <visibility>1</visibility>
           <Style id="default"></Style>
           <MultiGeometry>
           <Point>
        <extrude>0</extrude>
        <altitudeMode>relative</altitudeMode>
        <coordinates>""",
            ## KML is very fussy about not having spaces in these coordinates
            ## The next four lines are a work around
            line1 = "%f," % float(waypoints_geo[waypoint_type][index][LON]/10000000.0)
            line2 = "%f," % float(waypoints_geo[waypoint_type][index][LAT]/10000000.0)
            line3 = "%f" %  float(5) # Altitude forced to 5
            line = " " + line1 + line2 + line3
            print >> filename, line,
            print >> filename, """</coordinates>
        </Point>
          <Model>""",
            print >> filename,"""
            <Location>
               <longitude>""",
            print >> filename, waypoints_geo[waypoint_type][index][LON] / 10000000.0,
            print >> filename, """</longitude>
               <latitude>""",
            print >> filename, waypoints_geo[waypoint_type][index][LAT] / 10000000.0,
            print >> filename, """</latitude>
               <altitude>""",
            print >> filename, 5.0 ,
            print >> filename, """</altitude>
            </Location>
          <Orientation>
            <heading>0</heading>
            <tilt>0</tilt>
            <roll>0</roll>
          </Orientation>
          <Scale>
            <x>1</x>
            <y>1</y>
            <z>1</z>
          </Scale>
          <Link>
            <href>models/waypoint2.dae</href>
          </Link>
          </Model>
          </MultiGeometry>
          <DocumentSource>flan.py</DocumentSource>
        </Placemark>"""
            index += 1
         ####   
    return     
        
            
def generate_flown_waypoints_kml(waypoints_geo, filename,log_book, flight_clock) :
    """Print out KML to filename which specifies GE Placemarks for each waypoint.
    waypoints are provided to this routine as as list in waypoints_geo"""

    
    LON = 0
    LAT = 1
    ALT = 2
    COMMENT = 3

    NORMAL_WAYPOINT = 1
    RTL_WAYPOINT = 2
    print >> filename, """<Folder><open>0</open>
    <name>Waypoints</name>
    <description>Waypoints</description>"""
    for a_waypoint_flown in log_book.flown_waypoints :
        waypoint = a_waypoint_flown.waypointIndex
        print >> filename, """   <Placemark> 
      <name>""",
        if a_waypoint_flown.status == "011":
            print >> filename, "R",waypoint,"""</name>
      <description>""",
            waypoint_type = RTL_WAYPOINT
        else :
            print >> filename, "W",waypoint,"""</name>
      <description>""",
            waypoint_type = NORMAL_WAYPOINT
        print >> filename, waypoints_geo[waypoint_type][waypoint][COMMENT],
        print >> filename, """</description>"""
        print >> filename, """<TimeSpan>
      <begin>""",
        # Google Earth requires GPS time to be converted to an XML time format
        print >> filename, flight_clock.convert(a_waypoint_flown.start_time,log_book)
        print >> filename, """</begin>
        <end>""",    
        print >> filename, flight_clock.convert(a_waypoint_flown.end_time,log_book), 
        print >> filename, """</end>
      </TimeSpan>
       <visibility>1</visibility>
       <Style id="default"></Style>
       <MultiGeometry>
       <Point>
    <extrude>0</extrude>
    <altitudeMode>absolute</altitudeMode>
    <coordinates>""",
        ## KML is very fussy about not having spaces in these coordinates
        ## The next four lines are a work around
        line1 = "%f," % float(waypoints_geo[waypoint_type][waypoint][LON]/10000000.0)
        line2 = "%f," % float(waypoints_geo[waypoint_type][waypoint][LAT]/10000000.0)
        line3 = "%f" %  float(waypoints_geo[waypoint_type][waypoint][ALT]) # Altitude in waypoints.h already in meters
        line = "          " + line1 + line2 + line3
        print >> filename, line,
        print >> filename, """</coordinates>
    </Point>
      <Model>"""
        if log_book.ardustation_pos == "Recorded" :
             print >> filename, """
            <altitudeMode>relativeToGround</altitudeMode>"""
        else:
             print >> filename, """
            <altitudeMode>absolute</altitudeMode>"""
        print >> filename,"""
        <Location>
           <longitude>""",
        print >> filename, waypoints_geo[waypoint_type][waypoint][LON] / 10000000.0,
        print >> filename, """</longitude>
           <latitude>""",
        print >> filename, waypoints_geo[waypoint_type][waypoint][LAT] / 10000000.0,
        print >> filename, """</latitude>
           <altitude>""",
        if log_book.ardustation_pos == "Recorded" :
             print >> filename, 0 ,
        else: 
             print >> filename, waypoints_geo[waypoint_type][waypoint][ALT] ,
        print >> filename, """</altitude>
        </Location>
      <Orientation>
        <heading>0</heading>
        <tilt>0</tilt>
        <roll>0</roll>
      </Orientation>
      <Scale>
        <x>1</x>
        <y>1</y>
        <z>1</z>
      </Scale>
      <Link>
        <href>models/waypoint2.dae</href>
      </Link>
      </Model>
      </MultiGeometry>
      <DocumentSource>flan.py</DocumentSource>
    </Placemark>"""
    print >> filename, "</Folder>"
      
    return  

def create_flown_waypoint_kml(waypoint_filename,flight_origin,file_handle_kmz,flight_clock,log_book) :
    waypoints_geo = get_waypoints_list_in_absolute_lat_long(waypoint_filename,flight_origin)
    generate_flown_waypoints_kml(waypoints_geo, file_handle_kmz,log_book, flight_clock)
    message = "Parsing of " + waypoint_filename + "\n into KML Placemarks is complete"
    if debug:
        print message
    else :
        print "Waypoints flown analyzed, and converted to KML"
           
def calculate_headings_pitch_roll(log_book,flight_origin, options) :
    for entry in log_book.entries :
        entry.lon[GPS]  = entry.longitude / 10000000.0 # degrees
        entry.lat[GPS]  = entry.latitude  / 10000000.0 # degrees
        entry.alt[GPS]  = ( entry.altitude  / 100.0) + options.altitude_correction       # meters absolute
        abs_location = flight_origin.rel_to_absolute(entry.IMUlocationx_W1, entry.IMUlocationy_W1, \
                                       (entry.IMUlocationz_W1 * 100), entry.latitude)
        entry.lat[IMU] = abs_location[0] / 10000000.0
        entry.lon[IMU] = abs_location[1] / 10000000.0
        entry.alt[IMU] = ( abs_location[2] / 100.0 ) + options.altitude_correction
        # If using Ardustation, then roll and pitch already set from telemetry
        if log_book.ardustation_pos != "Recorded" : # only calc if using UAV DevBoard

            safe_rmat7 = entry.rmat7
            if safe_rmat7 > 16384 :
                safe_rmat7 = 16384
                print "Warning: rmat7 greater than abs(16384) at time of week ", entry.tm
            if safe_rmat7 < -16384 :
                safe_rmat7 = -16384
                print "Warning: rmat7 greater than 16384 at time of week ", entry.tm
            safe_rmat6 = entry.rmat6
            if safe_rmat6 > 16384 :
                safe_rmat6 = 16384
                print "Warning: rmat6 greater than abs(16384) at time of week ", entry.tm
            if safe_rmat6 <-16384 :
                safe_rmat6 = -16384
                print "Warning: rmat6 greater than abs(16384) at time of week ", entry.tm

            entry.pitch = (asin(safe_rmat7 / 16384.0) / (2*pi)) * 360 # degrees
            entry.roll =  (asin(safe_rmat6 / 16384.0) / (2*pi)) * 360

            # Allow for inverted flight
            if entry.rmat8 < 0 :
                entry.roll = 180 - entry.roll
            # Calcuate our heading from Rmat readings.
            heading_radians = atan2(- entry.rmat1 , entry.rmat4)
            entry.heading_degrees = (heading_radians / (2 * pi)) * 360
        
def write_style_urls(filename):
    for acolor in mycolors.list2 :
        temp_line = "      <Style id=\""  + acolor[0] + "\">"
        print >> filename, temp_line
        print >> filename, """        <LineStyle>"""
        temp_line = "          <color>" + "7f" + acolor[1] + "</color>"
        print >> filename, temp_line
        print >> filename, """          <width>4</width>
        </LineStyle>
        <PolyStyle>"""
        temp_line = "          <color>" + "7f" + acolor[1] + "</color>"
        print >> filename, temp_line
        print >> filename, """        </PolyStyle>
      </Style>"""

def write_waypoint_document_preamble(filename):
    """Write the beginning of a KML document for waypoints"""
    print >> filename , """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <open>1</open>
     <name>""",
    waypoint_name = re.sub("\.h","", options.waypoint_filename)
    if debug > 0 : print "Flight Log Name is ", waypoint_name
    split_path = os.path.split(waypoint_name)
    waypoint_name   = split_path[1]
    print >> filename, waypoint_name,
    print >> filename, """</name>\n<description>A list of waypoints</description>"""
    return

def write_document_preamble(log_book,filename, telemetry_filename):
    print >> filename , """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <open>1</open>
    <name>Flight Log """,
    flight_log_name = re.sub("\.[tT][xX][tT]","", telemetry_filename)
    if debug > 0 : print "Flight Log Name is ", flight_log_name
    split_path = os.path.split(flight_log_name)
    flight_log_name   = split_path[1]
    print >> filename, flight_log_name,
    print >> filename, """</name><description><b>Flight Settings</b><P> </P><TABLE>"""

    if log_book.F4 == "Recorded" :
        try:
            temporary = log_book.roll_stabilization
            print >> filename, "<TR><TD>ROLL_STABILIZATION</TD><TD>", log_book.roll_stabilization, "</TD></TR>"
        except:
            pass
        print >> filename, "<TR><TD>PITCH_STABILIZATION</TD><TD>",log_book.pitch_stabilization, "</TD></TR>"
        print >> filename, "<TR><TD>YAW_STABILIZATION_RUDDER</TD><TD>",log_book.yaw_stabilization_rudder, "</TD></TR>"
        print >> filename, "<TR><TD>YAW_STABILIZATION_AILERON</TD><TD>", log_book.yaw_stabilization_aileron, "</TD></TR>"
        print >> filename, "<TR><TD>AILERON_NAVIGATION</TD><TD>", log_book.aileron_navigation, "</TD></TR>"
        print >> filename, "<TR><TD>RUDDER_NAVIGATION</TD><TD>",  log_book.rudder_navigation, "</TD></TR>"
        print >> filename, "<TR><TD>USE_ALTITUDEHOLD</TD><TD>", log_book.use_altitudehold, "</TD></TR>"
        print >> filename, "<TR><TD>RACING_MODE</TD><TD>", log_book.racing_mode, "</TD></TR>"
  
    if log_book.F5 == "Recorded" :
        print >> filename, "<TR><TD>YAWKP_AILERON</TD><TD>", log_book.yawkp_aileron, "</TD></TR>"
        print >> filename, "<TR><TD>YAWKD_AILERON</TD><TD>",log_book.yawkd_aileron, "</TD></TR>"
        print >> filename, "<TR><TD>ROLLKP</TD><TD>",log_book.rollkp, "</TD></TR>"
        print >> filename, "<TR><TD>ROLLKD</TD><TD>", log_book.rollkd, "</TD></TR>"
        print >> filename, "<TR><TD>AILERON_BOOST</TD><TD>", log_book.aileron_boost, "</TD></TR>"        
    
    if log_book.F6 == "Recorded" :
        print >> filename, "<TR><TD>PITCHGAIN</TD><TD>", log_book.pitchgain, "</TD></TR>"
        print >> filename, "<TR><TD>PITCHKD</TD><TD>",log_book.pitchkd, "</TD></TR>"
        print >> filename, "<TR><TD>RUDDER_ELEV_MIX</TD><TD>",log_book.rudder_elev_mix, "</TD></TR>"
        print >> filename, "<TR><TD>ROLL_ELEV_MIX</TD><TD>", log_book.roll_elev_mix, "</TD></TR>"
        print >> filename, "<TR><TD>ELEVATOR_BOOST</TD><TD>", log_book.elevator_boost, "</TD></TR>"        
        
    if log_book.F7 == "Recorded" :
        print >> filename, "<TR><TD>YAWKP_RUDDER</TD><TD>", log_book.yawkp_rudder, "</TD></TR>"
        print >> filename, "<TR><TD>YAWKD_RUDDER</TD><TD>",log_book.yawkd_rudder, "</TD></TR>"
        print >> filename, "<TR><TD>RUDDER_BOOST</TD><TD>",log_book.rudder_boost, "</TD></TR>"
        print >> filename, "<TR><TD>RTL_PITCH_DOWN</TD><TD>", log_book.rtl_pitch_down, "</TD></TR>"        
        
    if log_book.F8 == "Recorded" :
        print >> filename, "<TR><TD>HEIGHTMAX</TD><TD>", log_book.heightmax, "</TD></TR>"
        print >> filename, "<TR><TD>HEIGHTMIN</TD><TD>",log_book.heightmin, "</TD></TR>"
        print >> filename, "<TR><TD>MINIMUMTHROTTLE</TD><TD>",log_book.minimumthrottle, "</TD></TR>"
        print >> filename, "<TR><TD>MAXIMUMTHROTTLE</TD><TD>", log_book.maximumthrottle, "</TD></TR>"
        print >> filename, "<TR><TD>PITCHATMINTHROTTLE</TD><TD>", log_book.pitchatminthrottle, "</TD></TR>"
        print >> filename, "<TR><TD>PITCHATMAXTHROTTLE</TD><TD>", log_book.pitchatmaxthrottle, "</TD></TR>"
        print >> filename, "<TR><TD>PITCHATZEROTHROTTLE</TD><TD>",  log_book.pitchatzerothrottle, "</TD></TR>"   
        
    print >> filename, "</TABLE><P> </P>"
    print >> filename, """</description>"""
  


def write_flight_path_preamble (log_book,filename):
    write_style_urls(filename)
    
      
def write_flight_path_postamble(log_book,filename):
    # print >> filename, """  </Folder>"""
    pass

def write_document_postamble(filename) :
    print >> filename, """</Document>
</kml>
 """

def insert_time_span(filename,begin_time,end_time,log_book) :
    """ print a KML TIME_SPAN sentence if using SERIAL_UDB format
    Do not print a KML TIME SPAN sentence for SERIAL_ARDUSTATION"""
    if log_book.ardustation_pos == "Recorded" :
        return()  # Don't insert a TimeSpan for ARDUSTATON format
    print >> filename, """<TimeSpan>
      <begin>""",
    print >> filename, begin_time,
    print >> filename, """</begin>
    <end>""",    
    print >> filename, end_time, 
    print >> filename, """</end>
      </TimeSpan>"""
    

def write_placemark_preamble_auto(open_waypoint,current_waypoint,filename,log_book,flight_clock,log_book_index):
    print >> filename, """<Placemark>"""
    begin_time = flight_clock.convert(log_book.entries[log_book_index].tm, log_book)
    end_time = flight_clock.convert(find_gps_time_of_next_waypoint(log_book.entries,log_book_index),log_book)
    insert_time_span(filename,begin_time,end_time,log_book)
    print >> filename, """<name>""",
    print >> filename, "Towards Waypoint: ", current_waypoint,
    print >> filename, """</name>"""
   
    if open_waypoint :
        print >> filename, "     <visibility>1</visibility>"
    else:
        print >> filename, "     <visibility>0</visibility>"
    print >> filename, """        <description>waypoint""",
    print >> filename, current_waypoint,
    print >> filename, "</description>"
    temp_line = "     <styleUrl>#" +  \
        mycolors.list[current_waypoint % 12][0] + "</styleUrl>"
    print >> filename, temp_line
    print >> filename, """        <LineString>
        <extrude>1</extrude>
        <tessellate>1</tessellate>"""
    if log_book.ardustation_pos == "Recorded" :
        print >> filename, """
      <altitudeMode>relativeToGround</altitudeMode>"""
    else:
        print >> filename, """
      <altitudeMode>absolute</altitudeMode>"""
    print >> filename, """
            <coordinates>"""
     
    
def write_placemark_postamble(filename):
    print >> filename, """        </coordinates>
      </LineString>
    </Placemark>"""

class flown_waypoint() :
    """Store start and end times of flight over a desired waypoint route"""
    def __init__ (self):
        self.start_time = 0
        self.end_time = 0
        self.waypoint = 0
        self.status = 0


def find_waypoint_start_and_end_times(log_book) :
    """Find and remember the start and end times of each waypoint route
    from the point of view of the flight recorded in the telemetry. This
    can then be used to create time spans for waypoint routes and waypoint placemarks
    later on in the script. It could also be used for creating "Finish Lines", that
    are automatically shown when the plane is close to a finish line later on in the
    development of flan.py"""
    first_time_through_loop = True
    log_book.flown_waypoints = [] # a new list flown_waypoints is being made in the log book
    entry_index = 0
    for entry in log_book.entries :
        if first_time_through_loop == True :
            a_flown_waypoint = flown_waypoint() # create new instance of flown_waypoint
            current_status = log_book.entries[entry_index].status # normally manual e.g. 110
            current_waypoint_index = log_book.entries[entry_index].waypointIndex
            a_flown_waypoint.start_time = log_book.entries[entry_index].tm
            a_flown_waypoint.waypointIndex = current_waypoint_index
            a_flown_waypoint.status = current_status
            first_time_through_loop = False
            if debug :
                print "Processing waypoint times:..."
        else :
            if ((log_book.entries[entry_index].status != current_status) or
                    (log_book.entries[entry_index].waypointIndex != current_waypoint_index)) :
                # Change of flight mode status or desired waypoint                
                a_flown_waypoint.end_time = log_book.entries[entry_index].tm
                log_book.flown_waypoints.append(a_flown_waypoint)
                # Have stored everything about last waypoint route, now move onto the next one ....
                a_flown_waypoint = flown_waypoint()
                current_status = log_book.entries[entry_index].status # normally manual e.g. 110
                current_waypoint_index = log_book.entries[entry_index].waypointIndex
                a_flown_waypoint.start_time = log_book.entries[entry_index].tm
                a_flown_waypoint.waypointIndex = current_waypoint_index
                a_flown_waypoint.status = current_status
        entry_index += 1
    a_flown_waypoint.end_time = log_book.entries[entry_index -1].tm
    log_book.flown_waypoints.append(a_flown_waypoint)

    
                 
def find_gps_time_of_next_waypoint(log_book_entries,entry_number):
    """ Look ahead to find time at which desired waypoint changes or
    the flight mode changes between manual/stabilized and waypoint mode"""
    current_status = log_book_entries[entry_number].status
    current_waypoint = log_book_entries[entry_number].waypointIndex
   
    index = entry_number
    while ( index < len(log_book_entries) ) :
        if (log_book_entries[index].status != current_status ):
            return(log_book_entries[index - 1].tm)
        if (log_book_entries[index].waypointIndex != current_waypoint) :
            return(log_book_entries[index - 1].tm)
        index += 1
    return(log_book_entries[index -1].tm)
            
    
def write_placemark_preamble_manual(open_waypoint,filename,log_book,flight_clock,log_book_index, \
                                    max_time_manual_entries, manual_start_time):
    print >> filename, """
    <Placemark>"""
    begin_time = flight_clock.convert(manual_start_time, log_book)
    end_time_of_next_waypoint = find_gps_time_of_next_waypoint(log_book.entries,log_book_index)
    time_diff = end_time_of_next_waypoint - manual_start_time
    # Here the code splits long periods of manual flight up into multiple route sections
    if time_diff > max_time_manual_entries :
        end_time_of_next_waypoint = manual_start_time + max_time_manual_entries
    end_time = flight_clock.convert(end_time_of_next_waypoint, log_book)
    insert_time_span(filename,begin_time,end_time,log_book)
    print >> filename, """
      <name>Manual Mode</name>
      <description>Manual Mode</description>"""
    
    if open_waypoint :
        print >> filename, "      <visibility>1</visibility>"
    else:
        print >> filename, "      <visibility>0</visibility>"
    print >> filename, """      <styleUrl>#red</styleUrl>"
            <LineString>
            <extrude>1</extrude>
            <tessellate>1</tessellate>"""
    if log_book.ardustation_pos == "Recorded" :
        print >> filename, """
            <altitudeMode>relativeToGround</altitudeMode>"""
    else :
        print >> filename, """
            <altitudeMode>absolute</altitudeMode>"""
    print >> filename, """
        <coordinates>"""
    return

def write_T3_waypoints(filename,origin,log_book)  :
     # note origin.latitude and origin.longitude are straight from log of telemetry
     # so they are expressed in degrees * 10,000,000
     initLat = origin.latitude / 10000000.0
     initLon = origin.longitude / 10000000.0
    
     corner = 100 # easy way to describe location of waypoints, e.g. 100m,100m from origin
     convert = 90.0 /10000000.0
    
     #wp_dist_in_lat = (corner * convert)  # in normal degrees
     #wp_dist_in_lon = (corner * convert) * (acos(((initLat)/360)*2*pi))
     waypoint_list = \
      [((corner * convert)+initLat,((corner * convert) /(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((corner * convert)+initLat,((-corner * convert)/(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((-corner * convert)+initLat,((corner * convert)/(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((-corner * convert)+initLat,((-corner * convert)/(cos(((initLat) / 360)*2*pi))) + initLon)]
     LAT = 0
     LON = 1
     print >> filename, """<Folder><open>0</open>
    <name>T3 Fig 8 Course</name>
    <description>The T3 Competition Course from DIYDrones.com</description>"""
     for waypoint in waypoint_list :
         print >> filename, """   <Placemark> 
      <name>Waypoint X</name>
      <description>Waypoint</description>
      <visibility>0</visibility>
       <Style id="default"></Style>
      <Model>"""
         if log_book.ardustation_pos == "Recorded" :
             print >> filename, """
            <altitudeMode>relativeToGround</altitudeMode>"""
         else:
             print >> filename, """
            <altitudeMode>absolute</altitudeMode>"""
         print >> filename,"""
        <Location>
           <longitude>""",
         print >> filename, waypoint[LON],
         print >> filename, """</longitude>
           <latitude>""",
         print >> filename, waypoint[LAT],
         print >> filename, """</latitude>
           <altitude>""",
         if log_book.ardustation_pos == "Recorded" :
             print >> filename, 0 ,
         else: 
             print >> filename, origin.altitude / 100.0 ,
         print >> filename, """</altitude>
        </Location>
      <Orientation>
        <heading>0</heading>
        <tilt>0</tilt>
        <roll>0</roll>
      </Orientation>
      <Scale>
        <x>1</x>
        <y>1</y>
        <z>1</z>
      </Scale>
      <Link>
        <href>models/waypoint.dae</href>
      </Link>
      </Model>
      <DocumentSource>Pete Hollands</DocumentSource>
    </Placemark>"""
     print >> filename, "</Folder>"

     # Create another folder for the Sparkfun building course.
    
     corner = 100 # easy way to describe location of waypoints, e.g. 100m,100m from origin
     convert = 90.0 /10000000.0
    
     #wp_dist_in_lat = (corner * convert)  # in normal degrees
     #wp_dist_in_lon = (corner * convert) * (acos(((initLat)/360)*2*pi))
     waypoint_list = \
      [((-10 * convert)+initLat,((26 * convert) /(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((-75 * convert)+initLat,((26 * convert)/(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((-75 * convert)+initLat,((-26 * convert)/(cos(((initLat) / 360)*2*pi))) + initLon), \
       ((-10 * convert)+initLat,((-26 * convert)/(cos(((initLat) / 360)*2*pi))) + initLon)]

     print >> filename, """<Folder><open>0</open>
    <name>T3 Sparkfun Course</name>
    <description>The T3 Sparkfun builing Course from DIYDrones.com<p>
    Using Relative Waypoints this course is (-10,26),(-75,26), (-75,-26),(-10,-26)</p><p>
    So the origin is 10m to the North of the center of the building.</p></description>"""
     for waypoint in waypoint_list :
         print >> filename, """   <Placemark> 
      <name>Waypoint X</name>
      <description>Waypoint</description>
      <visibility>0</visibility>
       <Style id="default"></Style>
      <Model>"""
         if log_book.ardustation_pos == "Recorded" :
             print >> filename, """
            <altitudeMode>relativeToGround</altitudeMode>"""
         else:
             print >> filename, """
            <altitudeMode>absolute</altitudeMode>"""
         print >> filename,"""
        <Location>
           <longitude>""",
         print >> filename, waypoint[LON],
         print >> filename, """</longitude>
           <latitude>""",
         print >> filename, waypoint[LAT],
         print >> filename, """</latitude>
           <altitude>""",
         if log_book.ardustation_pos == "Recorded" :
             print >> filename, 0 ,
         else: 
             print >> filename, origin.altitude / 100.0 ,
         print >> filename, """</altitude>
        </Location>
      <Orientation>
        <heading>0</heading>
        <tilt>0</tilt>
        <roll>0</roll>
      </Orientation>
      <Scale>
        <x>1</x>
        <y>1</y>
        <z>1</z>
      </Scale>
      <Link>
        <href>models/waypoint.dae</href>
      </Link>
      </Model>
      <DocumentSource>Pete Hollands</DocumentSource>
    </Placemark>"""
     print >> filename, "</Folder>"

def write_flight_path_inner(log_book,flight_origin, filename,flight_clock,primary_locator):
    first_waypoint = True
    open_waypoint = True      # We only open the first few waypoints in GE - to keep graphics clean
    max_waypoints_to_open = 9
    max_time_manual_entries = 25000 # time( milli secs)length of a manual route before starting new manual route
    log_book_index = 0
    for entry in log_book.entries :
        if log_book.ardustation_pos == "Recorded" :
            # If using Ardustation force colour coding of waypoints
            # as we don't have any status to know if we are in manual
            # or in stabilized or in Waypoint Mode.
            entry.status = "1111"
        # Waypoint mode can be matched by status .111 or status .11(New as of rev 327 of MatrixPIlot)
        match = re.match("^.11",entry.status) 
        if match :
            current_waypoint = entry.waypointIndex
            if first_waypoint :
                write_placemark_preamble_auto(open_waypoint,current_waypoint,filename,log_book,flight_clock,log_book_index)
                first_waypoint = False
                last_status_auto = True
            elif last_status_auto == False : # previous entry manual mode
                line1 = "%f," % entry.lon[primary_locator]
                line2 = "%f," % entry.lat[primary_locator]
                line3 = "%f" %  entry.alt[primary_locator]
                line = "          " + line1 + line2 + line3
                print >> filename, line
                write_placemark_postamble(filename)
                write_placemark_preamble_auto(open_waypoint,current_waypoint,filename,log_book,flight_clock,log_book_index)
                line1 = "%f," % entry.lon[primary_locator]
                line2 = "%f," % entry.lat[primary_locator]
                line3 = "%f" %  entry.alt[primary_locator]
                line = "          " + line1 + line2 + line3
                print >> filename, line
                last_status_auto = True
            else:       # Previous entry was also Auto Mode
                # Are we still aiming for the same waypoint ?  No  
                if  current_waypoint  != last_waypoint :
                    line1 = "%f," % entry.lon[primary_locator]
                    line2 = "%f," % entry.lat[primary_locator]
                    line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                    line = "          " + line1 + line2 + line3
                    print >> filename, line
                    write_placemark_postamble(filename)
                    write_placemark_preamble_auto(open_waypoint,current_waypoint,filename,log_book,flight_clock,log_book_index)
                    line1 = "%f," % entry.lon[primary_locator]
                    line2 = "%f," % entry.lat[primary_locator]
                    line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                    line = "          " + line1 + line2 + line3
                    print >> filename, line
                else : # We are still aiming for the same waypoint
                    line1 = "%f," % entry.lon[primary_locator]
                    line2 = "%f," % entry.lat[primary_locator]
                    line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                    line = "          " + line1 + line2 + line3
                    print >> filename, line                  
                    last_status_auto = True
            last_waypoint = current_waypoint
        else :  # we are currently in Manual Mode
            if first_waypoint :
                manual_start_time = log_book.entries[log_book_index].tm
                write_placemark_preamble_manual(open_waypoint,filename,log_book,flight_clock,log_book_index, \
                                               max_time_manual_entries, manual_start_time )
                first_waypoint  = False
                last_status_auto = False
            if last_status_auto == True :  # We've just changed from auto to Manual.
                manual_start_time = log_book.entries[log_book_index].tm
                line1 = "%f," % entry.lon[primary_locator]
                line2 = "%f," % entry.lat[primary_locator]
                line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                line = "          " + line1 + line2 + line3
                print >> filename, line
                write_placemark_postamble(filename)
                write_placemark_preamble_manual(open_waypoint,filename,log_book,flight_clock,log_book_index, \
                                               max_time_manual_entries, manual_start_time )
                line1 = "%f," % entry.lon[primary_locator]
                line2 = "%f," % entry.lat[primary_locator]
                line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                line = "          " + line1 + line2 + line3
                print >> filename, line
                first_waypoint  = False
                last_status_auto = False
            else : # We are still in manual, we were in manual last time.
                # print intermediary points 
                line1 = "%f," % entry.lon[primary_locator]
                line2 = "%f," % entry.lat[primary_locator]
                line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                line = "          " + line1 + line2 + line3
                print >> filename, line
                if log_book.entries[log_book_index].tm > (manual_start_time +  max_time_manual_entries):
                    write_placemark_postamble(filename)
                    manual_start_time = log_book.entries[log_book_index].tm
                    write_placemark_preamble_manual(open_waypoint,filename,log_book,flight_clock,log_book_index, \
                                               max_time_manual_entries, manual_start_time )
                    line1 = "%f," % entry.lon[primary_locator]
                    line2 = "%f," % entry.lat[primary_locator]
                    line3 = "%f" %  ( entry.alt[primary_locator] - 2 )
                    line = "          " + line1 + line2 + line3
                    print >> filename, line
            last_status_auto = False
        log_book_index += 1
    write_placemark_postamble(filename)
    return
    
def write_flight_path(log_book,flight_origin, filename,flight_clock):
    primary_locator = log_book.primary_locator
    write_flight_path_preamble(log_book,filename)
    #write_T3_waypoints(filename,flight_origin,log_book)
    if primary_locator == GPS :
        print >> filename, """     <Folder><open>0</open>
        <name>GPS Paths</name>
        <description>Coloured Coded GPS Paths to Waypoints<p> Manual Mode is Blue</p></description>"""
        write_flight_path_inner(log_book,flight_origin, filename,flight_clock,primary_locator)
        write_flight_path_postamble(log_book, filename)
        print >> filename, """      </Folder>"""
    elif primary_locator == IMU :
        print >> filename, """     <Folder><open>0</open>
        <name>IMU Paths</name>
        <description>Coloured Coded IMU Paths to Waypoints<p> Manual Mode is Blue</p></description>"""
        write_flight_path_inner(log_book,flight_origin, filename,flight_clock,primary_locator)
        write_flight_path_postamble(log_book, filename)
        print >> filename, """      </Folder>"""
        ### Also provide a GPS track for comparison
        print >> filename, """     <Folder><open>0</open>
        <name>GPS Paths</name>
        <description>Coloured Coded GPS Paths to Waypoints<p> Manual Mode is Blue</p></description>"""
        write_flight_path_inner(log_book,flight_origin, filename,flight_clock,GPS)
        write_flight_path_postamble(log_book, filename)
        print >> filename, """      </Folder>"""
        

class clock() :
    """ Generate a time sequence for use in KML and Google Earth"""
    def __init__(self) :
        # It would be good to initilise the telemetry date and time from the
        # telemetry log files and GPS reported time. But Currently we do not
        # record the week number in the telemetry so this is not possible.
        # So for now we use the time at which the telemety is converted. This
        # will then provide us with an animated sequence over time in GE. The
        # relative times will be correct, but absolute time will be wrong.
        # Class Clock is conceptually designed accomodate SERIAL_ARUDSTATION telemetry
        # format which does not actually have any time embedded in the data.
        self.time = datetime.datetime.now()
        self.difference = datetime.timedelta(seconds = 1)
        self.gps_week_no = 200 # An arbitary week number until we the true week_no in telemetry
        self.last_gps_time = 0 # keep track of the last gps time that has been seen.
        self.identical_gps_time_count = 0 # Number of consequtive idential gps time entries.
    def next(self) :
        """ Generate another time interval of time"""
        self.time = self.time + self.difference
        self.xml_time = self.time.strftime("%Y-%m-%dT%H:%M:%SZ")
        return ( self.xml_time)
    def convert(self, gps_time,log_book) :
        """ Convert GPS time (gps_tow) into XML time for use in KML"""
        if log_book.F13 == "Recorded" : # If we have GPS week number from telemetry
            # Emebed the exact date and gps time in the GE Animation.
            x = datetime.datetime(1980, 1, 6) # This is week 0 of GPS time
            y = datetime.timedelta(7*log_book.gps_week, 0) # (days, seconds) Convert GPS week number
            z =datetime.timedelta(seconds = int(gps_time / 1000)) # convert seconds from saturday midnight
            time = x + y + z # These are intelligent time objects so can be summed
        else :
            # Use the date from when flan.pyw is being run as the animation date
            difference = datetime.timedelta(seconds = int(gps_time / 1000))
            time = self.time + difference
        xml_time = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        return (xml_time)
    
    def synthesize(self,gps_time):
       """Create synthetic time between entries which have identical gps time"""
       assumed_telemetry_time_delta = 250     # expected time difference between telemetry entries in ms
       if gps_time == self.last_gps_time :
           self.identical_gps_time_count += 1
           if self.identical_gps_time_count > 4 :
               print "Warning: More than 4 identical telemetry entries with identical time stamps"
               print "at gps time:", gps_time
           return(gps_time + assumed_telemetry_time_delta)
       else:
           self.last_gps_time = gps_time
           self.identical_gps_time_count = 0
           return(gps_time)

def write_earth_mag_vectors(log_book,filename, flight_clock):
    """write the recorded earth magnetic vectors to KML"""
    primary_locator = log_book.primary_locator
    print >> filename, """
      <Folder>
        <open>0</open>
    <name>Earth Magnetic Vectors""",
    print >> filename, "</name>"
    counter = 0
    print >> filename, "<description>Magnetic Vectors rotated into the Earth reference</description>"
    for entry in log_book.entries :
        counter += 1 
        line1 = "%f," % entry.lon[primary_locator]
        line2 = "%f," % entry.lat[primary_locator]
        line3 = "%f"  % entry.alt[primary_locator]
        line = line1 + line2 + line3
        #when = flight_clock.xml_time # Get the next time in XML format e.g.2007-01-14T21:05:02Z
        when = flight_clock.convert(entry.tm, log_book)
        print >> filename, """   <Placemark>"""
        print >> filename, """<TimeStamp>
        <when>""", when, """</when>
        </TimeStamp>
      <name>Vector""",
        print >> filename, counter,
        print >> filename, """</name>
      <description>Mag Vector""",
        print >> filename,  counter ,
        print >> filename,  \
               "<p>GPS Time(Secs)", (entry.tm /1000),\
               "</p><p>status",entry.status, "</p>", \
               "<p>Desired waypoint",entry.waypointIndex, "</p>", \
               "<p>Earth Mag Vec East",int(entry.earth_mag_vec_E), "</p>", \
               "<p>Earth Mag Vec North",int(entry.earth_mag_vec_N),"</p>", \
               "<p>Earth Mag Vec Down (Z)", int(entry.earth_mag_vec_Z), "</p>", \
               "</description>",
        print >> filename,"""
        <visibility>0</visibility>"""
        print >> filename, """       <Style id="default"></Style>
      <Model>"""
        if log_book.ardustation_pos == "Recorded" :
            print >> filename, """
      <altitudeMode>relativeToGround</altitudeMode>"""
        else:
            print >> filename, """
      <altitudeMode>absolute</altitudeMode>"""
        print >> filename, """
      <Location>
        <longitude>""",
        print >> filename,  entry.lon[primary_locator],
        print >> filename, """</longitude>
        <latitude>""",
        print >> filename, entry.lat[primary_locator],
        print >> filename, """</latitude>
        <altitude>""",
        print >> filename, entry.alt[primary_locator] + 10.0,
        print >> filename, """</altitude>
      </Location>
      <Orientation>
        <heading>""",
        earth_mag_heading = (((atan2(entry.earth_mag_vec_E,entry.earth_mag_vec_N) /
                              (2.0 * pi))* 360.0))
        print >> filename, earth_mag_heading,
        print >> filename, """</heading>
        <tilt>""",
        print >> filename, 0,
        print >> filename, """</tilt>
        <roll>""",
        print >> filename, 0,
        print >> filename, """</roll>
      </Orientation>
      <Scale>
        <x>2</x>
        <y>2</y>
        <z>2</z>
        </Scale>
      <Link>
        <href>models/mag_arrow.dae</href>
      </Link>
      </Model>
      <DocumentSource>Pete Hollands</DocumentSource>
    </Placemark>
"""
    # This marks the end of the for loop
    print >> filename, "</Folder>"

def write_earth_wind_2d_vectors(log_book,filename, flight_clock):
    primary_locator = log_book.primary_locator
    """write the recorded earth wind vectors (2D) to KML"""
    print >> filename, """
      <Folder>
        <open>0</open>
    <name>Earth Wind 2D Vectors""",
    print >> filename, "</name>"
    counter = 0
    print >> filename, "<description>Wind Vectors (2D) rotated into the Earth reference</description>"
    for entry in log_book.entries :
        counter += 1 
        #when = flight_clock.xml_time # Get the next time in XML format e.g.2007-01-14T21:05:02Z
        when = flight_clock.convert(entry.tm, log_book)
        print >> filename, """   <Placemark>"""
        print >> filename, """<TimeStamp>
        <when>""", when, """</when>
        </TimeStamp>
      <name>Vector""",
        print >> filename, counter,
        print >> filename, """</name>
      <description>Wind Vector""",
        print >> filename,  counter ,
        print >> filename,  \
               "<p>GPS Time(Secs)", (entry.tm /1000),\
               "</p><p>status",entry.status, "</p>", \
               "<p>Desired waypoint",entry.waypointIndex, "</p>", \
               "<p>Wind Vector X, East",int(entry.est_wind_x ), "</p>", \
               "<p>Wind Vector Y, North",int(entry.est_wind_y),"</p>", \
               "<p>Wind Vector Z, Up", int(entry.est_wind_z), "</p>", \
               "</description>",
        print >> filename,"""
        <visibility>0</visibility>"""
        print >> filename, """       <Style id="default"></Style>
      <Model>"""
        if log_book.ardustation_pos == "Recorded" :
            print >> filename, """
      <altitudeMode>relativeToGround</altitudeMode>"""
        else:
            print >> filename, """
      <altitudeMode>absolute</altitudeMode>"""
        print >> filename, """
      <Location>
        <longitude>""",
        print >> filename,  entry.lon[primary_locator],
        print >> filename, """</longitude>
        <latitude>""",
        print >> filename, entry.lat[primary_locator],
        print >> filename, """</latitude>
        <altitude>""",
        print >> filename, entry.alt[primary_locator] + 15.0,
        print >> filename, """</altitude>
      </Location>
      <Orientation>
        <heading>""",
        wind_heading = (((atan2( entry.est_wind_x , entry.est_wind_y ) /
                              (2.0 * pi))* 360.0))
        print >> filename, wind_heading,
        print >> filename, """</heading>
        <tilt>""",
        print >> filename, 0,
        print >> filename, """</tilt>
        <roll>""",
        print >> filename, 0,
        print >> filename, """</roll>
      </Orientation>
      <Scale>
        <x>0.02</x>"""
        wind_vector_2d_magnitude = ( sqrt(entry.est_wind_x ** 2 + entry.est_wind_y ** 2) ) / 10000
        print >> filename, "<y>", wind_vector_2d_magnitude,"</y>"
        print >> filename, """
        <z>0.02</z>
        </Scale>
      <Link>
        <href>models/arrow.dae</href>
      </Link>
      </Model>
      <DocumentSource>Pete Hollands</DocumentSource>
    </Placemark>
"""
    # This marks the end of the for loop
    print >> filename, "</Folder>"

               
def write_flight_vectors(log_book,origin, filename, flight_clock,gps_delay) :
    primary_locator = log_book.primary_locator
    print >> filename, """
      <Folder>
        <open>0</open>
    <name>Pitch/Roll/Yaw""",
    print >> filename, "</name>"
    counter = 0
    print >> filename, "<description>Model plane plotted for each second of flight</description>"
    for entry in log_book.entries :
      counter += 1
      if counter <= gps_delay :
        next
      else :
        line1 = "%f," % entry.lon[primary_locator]
        line2 = "%f," % entry.lat[primary_locator]
        line3 = "%f"  % entry.alt[primary_locator]
        line = line1 + line2 + line3
        #flight_clock.next()
        #when = flight_clock.xml_time # Get the next time in XML format e.g.2007-01-14T21:05:02Z
        when = flight_clock.convert(entry.tm,log_book)
        print >> filename, """   <Placemark>"""
        print >> filename, """<TimeStamp>
        <when>""", when, """</when>
        </TimeStamp>
      <name>Vector""",
        print >> filename, counter,
        print >> filename, """</name>
      <description>UAV Yaw Vector""",
        print >> filename,  counter ,
        print >> filename,  \
               "<p>NOTE: all the following data relates to GPS position (not IMU)</p>", \
               "<p>GPS Time(Secs)", (entry.tm /1000),\
               "</p><p>status",entry.status, "</p>", \
               "<p>Desired waypoint",entry.waypointIndex, "</p>", \
               "<p>Altitude above origin",int((entry.altitude - origin.altitude) / 100.0), "</p>", \
               "<p>Meters North of origin",int(((entry.latitude - origin.latitude) / 90.0)),"</p>", \
               "<p>Meters East of origin", int(((entry.longitude - origin.longitude) /90.0) \
                      * cos(entry.latitude /10000000 * (pi / 180))), "</p>", \
               "<p>GPS SOG", (entry.sog / 100.0),"</p>",\
               "<p>GPS COG",(entry.cog / 100.0),"</p></description>"
        print >> filename, """<visibility>0</visibility>"""
        print >> filename, """       <Style id="default"></Style>
      <Model>"""
        if log_book.ardustation_pos == "Recorded" :
            print >> filename, """
      <altitudeMode>relativeToGround</altitudeMode>"""
        else:
            print >> filename, """
      <altitudeMode>absolute</altitudeMode>"""
        print >> filename, """
      <Location>
        <longitude>""",
        print >> filename,  entry.lon[primary_locator],
        print >> filename, """</longitude>
        <latitude>""",
        print >> filename, entry.lat[primary_locator],
        print >> filename, """</latitude>
        <altitude>""",
        print >> filename, entry.alt[primary_locator],
        print >> filename, """</altitude>
      </Location>
      <Orientation>
        <heading>""",
        if log_book.ardustation_pos == "Recorded" :
            print >> filename, entry.cog / 100.0 ,
        else :
            print >> filename, log_book.entries[counter - (gps_delay + 1)].heading_degrees,
        print >> filename, """</heading>
        <tilt>""",
        print >> filename, log_book.entries[counter - (gps_delay + 1)].pitch,
        print >> filename, """</tilt>
        <roll>""",
        print >> filename, log_book.entries[counter - (gps_delay + 1)].roll,
        print >> filename, """</roll>
      </Orientation>
      <Scale>
        <x>2</x>
        <y>2</y>
        <z>2</z>
        </Scale>
      <Link>
        <href>models/block_plane.dae</href>
      </Link>
      </Model>
      <DocumentSource>Pete Hollands</DocumentSource>
    </Placemark>
"""
    # This marks the end of the for loop
    print >> filename, "</Folder>"
    
class origin() : 
    """ This class calculates and stores the flight origin of the plane"""
    def __init__(self):
        self.latitude = 0
        self.longitude = 0
        self.altitude = 0
        self.absolute_position = [0,0,0] # A temporary store of lat,lon,and alt above sea
        
    def average(self,initial_points,log_book) :
        """ obsolete method of finding the origin. It is no close enough
        to the algorithm used by the plane and so can cause in-consistancies"""
        index = 0
        sum_latitude = 0
        sum_longitude = 0
        sum_altitude = 0
        while ( index < initial_points ):
            index += 1
            # Average out first few reading to get our origin
            sum_latitude  += log_book.entries[index].latitude
            if debug: print "TOW:",log_book.entries[index].tm,
            if debug: print "lat", log_book.entries[index].latitude,
            if debug: print "sum_lat, ", sum_latitude, 
            sum_longitude += log_book.entries[index].longitude
            if debug: print "lon", log_book.entries[index].latitude,
            if debug: print "sum_lon, ", sum_longitude,
            sum_altitude  += log_book.entries[index].altitude
            if debug: print "sum_alt, ",  sum_altitude 
            if (index  == initial_points) :
                self.latitude =  sum_latitude  /  initial_points
                self.longitude = sum_longitude /  initial_points
                self.altitude =  sum_altitude  /  initial_points
                if debug :
                    print "init_lat: ",self.latitude,"init_lon: ", \
                            self.longitude,"init_alt: ",self.altitude
                    
    def calculate(self, log_book) :
        """Calculate the most likely origin from using the telemetry"""
        # STANDY_PAUSE is from defines.h of MatrixPilot. It determines
        # how long the plane waits after getting a nav_valid from the GPS
        # before storing the origin.
        STANDBY_PAUSE = 48
        background_timer_resolution = 0.5
        initial_nav_valid_time = 0
        msec_before_storing_origin =int(STANDBY_PAUSE * background_timer_resolution * 1000)
        for entry in log_book.entries :
            if debug : print entry.tm, entry.status
            match = re.match("^.1.*", entry.status ) # nav_valid
            if match :
                initial_nav_valid_time = entry.tm
                if debug : print "initial nav valid time", initial_nav_valid_time 
                break
        if initial_nav_valid_time == 0 :
            # Have not been able to find any entries with a valid GPS and radio on.
            message =  "There does not appear to be any valid GPS positions in this file. So it \n" + \
            "is not possible to plot this file in Google Earth\n" + \
            "Exiting Program"
            
            showerror(title = "No Valid GPS positions found in this telemetry file", message = message)
            print message
            exit(0) # We exit the program. Note that we did leave a kml file around
        time_to_acquire_origin = initial_nav_valid_time + msec_before_storing_origin
        if debug: print "time of acquiring origin will be ",time_to_acquire_origin
        for entry in log_book.entries :
            if debug : print "Got origin entry at ", entry.tm
            if entry.tm >= time_to_acquire_origin :
                self.latitude =  entry.latitude
                self.longitude = entry.longitude
                self.altitude =  entry.altitude
                if debug: print "Origin: Lat:",self.latitude,"Lon:",self.longitude,"Atl:",self.altitude
                break
        return

    def absolute_to_rel(lat,lon,alt_from_sea):
        """Convert an absolute lat,long,alt, to meters from origin as used by matrixpilot"""
        pass

    def rel_to_absolute(self,meters_east, meters_north, alt_from_origin, lat):
        """Convert meters east and north  from origin into an absolute lat and lon, alt from sea level"""
        delta_lon = convert_meters_east_to_lon(int(meters_east),lat)
        abs_lon  = int(self.longitude + int(delta_lon))
        abs_lat   = int(convert_meters_north_to_lat(meters_north) + self.latitude)
        abs_alt   = alt_from_origin + self.altitude
        self.absolute_position = [abs_lat, abs_lon, abs_alt]
        return self.absolute_position
                 
class flight_log_book:
    def __init__(self) :
        self.entries = [] # an empty list of entries  at the beginning.
        self.F4 = "Empty"
        self.F5 = "Empty"
        self.F6 = "Empty"
        self.F7 = "Empty"
        self.F8 = "Empty"
        self.F11 = "Empty"
        self.F13 = "Empty"
        self.ardustation_pos = "Empty"

def calc_average_wind_speed(log_book):
    if log_book.racing_mode == 0 :
        print "Average wind speed is only calculated if racing_mode = 1\n" + \
              "so that the plane is at a known constant throttle setting"
        return
    HAVE_DATA = 0
    AVERAGE = 1
    REMEMBER = 2
    acceptable_pitch = 5  # acceptable climb or descent in degrees that does not
                          #speed up or slow down the plane too much for this analysis
    
    compass_points = ["N  ","NNE","NE ","ENE", \
                      "E  ","ESE","SE ","SSE", \
                      "S  ","SSW","SW ","WSW", \
                      "W  ","WNW","NW ","NNW"  ]
    # We store average wind for 16 points of the compass
    # False means we have not had any value yet for that direction.
    wind_speeds = [ [False,0,[]],[False,0,[]],[False,0,[]],[False,0,[]], \
                        [False,0,[]],[False,0,[]],[False,0,[]],[False,0,[]], \
                        [False,0,[]],[False,0,[]],[False,0,[]],[False,0,[]], \
                        [False,0,[]],[False,0,[]],[False,0,[]],[False,0,[]], ]
    for entry in log_book.entries :
        if (entry.pitch > acceptable_pitch) or (entry.pitch < - acceptable_pitch) :
            continue # Plane is diving or climbing too much           
        cog_degrees = entry.cog / 100.0
        sog_meters = entry.sog / 100.0
        if sog_meters < 1.5 :# meters per second.
                continue # ignore - assume plane has taken off or landed
        else :
            if cog_degrees > 360 or cog_degrees < 0 :
                print "COG is invalid = ", cog_degrees
            direction = int (cog_degrees / 22.5) # 11.25 degrees is 1/16 of compass
            wind_speeds[direction][REMEMBER].append(sog_meters)

    # Ok we have all the value in buckets now create averages
    for wind_direction in wind_speeds :
        sum_of_sog = 0
        no_of_entries = 0
        for sogs in wind_direction[REMEMBER]:
            sum_of_sog = sum_of_sog  + sogs
            no_of_entries += 1
        average = sum_of_sog / no_of_entries
        wind_direction[AVERAGE] = average
    for i in 0,1,2,3,4,5,6,7 :
        print "Average SOG " , compass_points[i], " %4.1f" % wind_speeds[i][AVERAGE] ,\
              "Samples: %4s" % len(wind_speeds[i][REMEMBER]), \
              "  ", compass_points[i+8], " %4.1f" % wind_speeds[i+8][AVERAGE], \
              "Samples: %4s" % len(wind_speeds[i+8][REMEMBER]), \
              "Difference: %4.1f"  % abs(wind_speeds[i][AVERAGE] - wind_speeds[i+8][AVERAGE]) 

def create_waypoint_kmz(options):
    """Read a waypoint file, interpret the data and represent it in a
    KML file that can be viewed in Google Earth. Only use this routine
    when you are certain that the file does not have a movable origin"""
    f_pos = open(options.GE_filename_kml, 'w')
    write_waypoint_document_preamble(f_pos)
    flight_origin = origin()  ### Create a dummy flight origin - it will not be used
    waypoints_geo = get_waypoints_list_in_absolute_lat_long(options.waypoint_filename,flight_origin)
    generate_waypoints_kml(waypoints_geo,f_pos)
    write_document_postamble(f_pos)
    f_pos.close()
    return
        
def create_telemetry_kmz(options,log_book):          
    """Read a telemetry file, interpret the data and represent it in a
    KML file that can be viewed in Google Earth"""
    telemetry_filename = options.telemetry_filename
    waypoint_filename = options.waypoint_filename
    GE_filename = options.GE_filename
    CSV_filename = options.CSV_filename
    
    f_pos = open(options.GE_filename_kml, 'w')
    flight_origin = origin()
    if log_book.F13 != "Recorded" :
        flight_origin.calculate(log_book) # Telemetry never gave us the origin
        print "Origin calculated - no specific origin sent by telemetry"
    else :
        flight_origin.longitude = log_book.origin_east
        flight_origin.latitude = log_book.origin_north
        flight_origin.altitude = log_book.origin_altitude
        print "Using origin information received from telemetry"
    calculate_headings_pitch_roll(log_book, flight_origin, options)
    write_document_preamble(log_book,f_pos,telemetry_filename)
    if (options.waypoint_selector == 1):
        find_waypoint_start_and_end_times(log_book)
        create_flown_waypoint_kml(waypoint_filename,flight_origin,f_pos,flight_clock,log_book)
    if log_book.primary_locator == GPS:
        print "Using GPS data for plotting waypoint routes"
    elif log_book.primary_locator == IMU :
        print "Using IMU Locations for plotting waypoint routes"
    else:
        print "ERROR: Nonsensical data location type in create_telemetry_kmz()"
    write_flight_path(log_book,flight_origin,f_pos,flight_clock)
    gps_delay = options.gps_delay_correction
    print "GPS Delay Correction is set to ", gps_delay 
    write_flight_vectors(log_book,flight_origin,f_pos,flight_clock,gps_delay)
    if ( log_book.earth_mag_set == TRUE):
        write_earth_mag_vectors(log_book,f_pos, flight_clock)
    if ( log_book.wind_set == TRUE):
         write_earth_wind_2d_vectors(log_book,f_pos, flight_clock)

    write_document_postamble(f_pos)
    f_pos.close()

def create_log_book(options) :
    """Parse the telemetryfile and create a virtual flight log book object"""
    f = open(options.telemetry_filename, 'r')
    roll = 0  # only used with ardustation roll
    pitch = 0 # only used with ardustation pitch
    line_no = 0
    telemetry_restarts = 0 # Number of times we see telemetry re-start
    skip_entry = 3 # hack required as first entry can have wrong status in telemetry
                            # e.g. first status 100 even though GPS is good, second entry will
                            # be 110 . Status can take a moment to reflect good GPS.
    miss_out_interval = 0   # set to 3, 7, 15 for large datasets that slow down Google Earth
    if miss_out_interval > 0 :
        print "Note: miss_out_interval set to ", miss_out_interval, "telemetry entries"
    miss_out_counter  = 0
    max_tm_actual = 0
    log_book = flight_log_book()
    log_book.earth_mag_set = False 
    log_book.wind_set = False
    log_book.dead_reckoning = 0 # By default dead reckoning is off
    log_book.primary_locator = GPS # Default is to use GPS for plotting plane position.
    for line in f :
        line_no += 1
        log = telemetry() # Make a new empty log entry
        log_format  = log.parse(line,line_no, max_tm_actual)
        if log_format == "HKGCS_BLANK_LINE" : # blank line in Happy Killmore's GCS
            continue  # Go fetch another line
        if log_format == "Error" :# we had an error
            print "Error parsing telemetry line ",line_no 
            continue  # Go get the next line
        elif log_format == "F1" or log_format == "F2"  or \
               log_format == "ARDUSTATION!!!": # We have a normal telemetry line
            if debug : print "lat",log.latitude,"lon",log.longitude,"alt",log.altitude, \
                "wp", log.waypointIndex, "rmat1", log.rmat1
            if (log.latitude == 0 or log.longitude == 0 or log.altitude ==0 ):
                if debug: print "lat or long or alt is 0; ignoring line", line_no
                continue # Get next line of telemetry  - can happen at boot time on plane 
            else :
                # We have a good log entry - put it in the logbook.
                miss_out_counter += 1
                if log_format == "ARDUSTATION!!!" :
                        log_book.ardustation_pos = "Recorded"
                        log.roll = roll   # add the last roll parsed from Ardustation +++
                        log.pitch = pitch # add the last pitch parsed from Ardustation +++
                if skip_entry > 0 :
                    skip_entry -= 1
                    continue # get next line of telemetry
                if ((log.earth_mag_vec_E != 0 ) or (log.earth_mag_vec_N != 0 ) or (log.earth_mag_vec_Z != 0 )):
                    log_book.earth_mag_set = True
                if ((log.est_wind_x != 0 ) or (log.est_wind_y != 0 )or (log.est_wind_z != 0 )):
                    log_book.wind_set = True
                if max_tm_actual < log.tm_actual :
                    max_tm_actual = log.tm_actual  # record max_tm_actual for TOW week rollover case
                if (log_book.dead_reckoning == 1 ) and((log.IMUlocationx_W1 !=0 ) or (log.IMUlocationy_W1 != 0)): # IMUlocation is active, use it
                    log_book.primary_locator = IMU
                log.tm = flight_clock.synthesize(log.tm) # interpolate time between identical entries
                if (miss_out_counter > miss_out_interval) :# only store log every X times for large datasets
                    log_book.entries.append(log)
                    miss_out_counter = 0
        elif log_format == "F4" : # We have a type of options.h line
            # format of roll_stabilization has changed over time
            try:
                log_book.roll_stabilization        = log.roll_stabilization
            except:
                pass
            log_book.pitch_stabilization       = log.pitch_stabilization
            log_book.yaw_stabilization_rudder  = log.yaw_stabilization_rudder
            log_book.yaw_stabilization_aileron = log.yaw_stabilization_aileron
            log_book.aileron_navigation        = log.aileron_navigation
            log_book.rudder_navigation         = log.rudder_navigation
            log_book.use_altitudehold          = log.use_altitudehold
            log_book.racing_mode               = log.racing_mode
            log_book.F4 = "Recorded"
            telemetry_restarts += 1
        elif log_format == "F5" : # We have a type of options.h line
            log_book.yawkp_aileron = log.yawkp_aileron
            log_book.yawkd_aileron = log.yawkd_aileron
            log_book.rollkp = log.rollkp
            log_book.rollkd = log.rollkd
            log_book.aileron_boost = log.aileron_boost
            log_book.F5 = "Recorded"
        elif log_format == "F6" : # We have a type of options.h line
            log_book.pitchgain = log.pitchgain
            log_book.pitchkd = log.pitchkd
            log_book.rudder_elev_mix = log.rudder_elev_mix
            log_book.roll_elev_mix = log.roll_elev_mix
            log_book.elevator_boost = log.elevator_boost
            log_book.F6 = "Recorded"
        elif log_format == "F7" : # We have a type of options.h line
            log_book.yawkp_rudder = log.yawkp_rudder
            log_book.yawkd_rudder = log.yawkd_rudder
            log_book.rudder_boost = log.rudder_boost
            log_book.rtl_pitch_down = log.rtl_pitch_down
            log_book.F7 = "Recorded"
        elif log_format == "F8" : # We have a type of options.h line
            log_book.heightmax = log.heightmax
            log_book.heightmin = log.heightmin
            log_book.minimumthrottle = log.minimumthrottle
            log_book.maximumthrottle = log.maximumthrottle
            log_book.pitchatminthrottle = log.pitchatminthrottle
            log_book.pitchatmaxthrottle = log.pitchatmaxthrottle
            log_book.pitchatzerothrottle = log.pitchatzerothrottle
            log_book.F8 = "Recorded"
        elif (log_format == "F11") or (log_format == "F14") : # We have a type of options.h line
            ## BUILDING: All the F11 data variables need saving here ...
            log_book.dead_reckoning = log.dead_reckoning
            log_book.F11 = "Recorded"
        elif log_format == "F13" : # We have origin information from telemetry
            log_book.gps_week = log.gps_week
            log_book.origin_north = log.origin_north
            log_book.origin_east = log.origin_east
            log_book.origin_altitude = log.origin_altitude
            log_book.F13 = "Recorded"
        elif log_format == "ARDUSTATION+++" : # Intermediate Ardustation line
            roll = log.roll
            pitch = log.pitch
        else :
            print "Parsed a line format - ,", log_format, \
                  "but don't know what to do with it."
        
    initial_points = 10 # no. log entries to find origin at start
    
    f.close()

    if telemetry_restarts > 1 :
        showinfo(title ="Multiple Telemetry Starts in this File\n" ,      
                       message = "It appears that this telemetry has multiple\n" +
                        "re-starts. Please proceed carefully. Re-starts can be\n"      +
                        "an indicator of the UDB re-booting spontaneously in flight\n"  +
                        "If you powered up your UDB, and then pressed the reset, then\n"   +
                        "this will explain the multiple restarts.\n"             +
                        "\n"                                                       +
                        "It is best if flan.py does not have multiple telemetry\n"          +
                        "starts in it's input file. This might confuse flan.py as\n"  +    
                        "to which origin can be used for position and altitude.\n"   +
                        "" )
    return(log_book)
        
def wrap_kml_into_kmz(options):
    flight_pos_kmz = options.GE_filename
    # Try to find a models directory nearby to add to zip files....
    model_dir = []
    model_dir.append(os.path.join(os.getcwd(), "models"))  
    if (os.access(os.path.join(model_dir[0],"waypoint.dae"),os.F_OK)) and \
           (os.access(os.path.join(model_dir[0],"block_plane.dae"),os.F_OK)) and \
           (os.access(os.path.join(model_dir[0],"arrow.dae"),os.F_OK)):
        dir_index = 0 
    else: 
        message =  "Program currently needs the models directory (part of the Tools/flan download)\n" + \
            "to be placed, with it's internal file contents, in the directory containing\n" + \
            "flan.py \n" + \
            "Exiting Program"
        showerror(title = "Missing Models Directory and some associated file", message = message)
        print message
        exit(0) # We exit the program. Note that we did leave a kml file around
    waypoint_model  = os.path.join("models","waypoint.dae")
    block_plane_model = os.path.join("models","block_plane.dae")
    arrow_model = os.path.join("models","arrow.dae")
    waypoint2_model = os.path.join("models","waypoint2.dae")
    mag_arrow_model = os.path.join("models","mag_arrow.dae")
    kmzfile = ZipFile(flight_pos_kmz, "w",ZIP_DEFLATED) # "a" to append, "r" to read
    kmzfile.write(options.GE_filename_kml)
    kmzfile.write(waypoint_model)
    kmzfile.write(block_plane_model)
    kmzfile.write(arrow_model)
    kmzfile.write(waypoint2_model)
    kmzfile.write(mag_arrow_model)
    kmzfile.close()
    # Remove the temporary kml files, now we have the kmz file
    os.remove(options.GE_filename_kml)
    return

def write_csv(options,log_book):
    ### write out a csv file enabling analysis in Excel or OpenOffice
   
    f_csv = open(options.CSV_filename, 'w')
    print >> f_csv, "Time (secs), Status, Lat, Lon,Waypoint, Altitude, Pitch, Roll, Heading, COG, SOG, CPU, SVS, VDOP, HDOP,",
    print >> f_csv, "Est AirSpd, Est X Wind, Est Y Wind, Est Z Wind,IN1,IN2,IN3,IN4,",
    print >> f_csv, "IN5,IN6,IN7,IN8,OUT1,OUT2,OUT3,OUT4,",
    print >> f_csv, "OUT5,OUT6,OUT7,OUT8,LEX,LEY,LEZ,IMU X,IMU Y,IMU Z,MAG W,MAG N,MAG Z"
    for entry in log_book.entries :
        print >> f_csv, entry.tm / 1000.0, ",", entry.status, "," , \
              entry.latitude / 10000000.0, ",",entry.longitude / 10000000.0,",", \
              entry.waypointIndex, ",", int (entry.altitude / 100.0) , "," , \
              int(-entry.pitch), ",", int(-entry.roll), ",", int(entry.heading_degrees) , "," , \
              entry.cog / 100.0 , "," , entry.sog / 100.0,",", entry.cpu,",", entry.svs, \
              ",", entry.vdop, ",", entry.hdop, "," , \
              entry.est_airspeed, "," , entry.est_wind_x, "," , entry.est_wind_y, ",", entry.est_wind_z , "," , \
              entry.pwm_input[1], "," , entry.pwm_input[2], "," , entry.pwm_input[3], "," , entry.pwm_input[4], "," , \
              entry.pwm_input[5], "," , entry.pwm_input[6], "," , entry.pwm_input[7], "," , entry.pwm_input[8], "," , \
              entry.pwm_output[1], "," , entry.pwm_output[2], "," , entry.pwm_output[3], "," , entry.pwm_output[4], "," , \
              entry.pwm_output[5], "," , entry.pwm_output[6], "," , entry.pwm_output[7], "," , entry.pwm_output[8], "," , \
              entry.lex, "," , entry.ley , "," , entry.lez, ",", \
              entry.IMUlocationx_W1, ",", entry.IMUlocationy_W1, ",", entry.IMUlocationz_W1, "," , \
              int(entry.earth_mag_vec_E), "," , int(entry.earth_mag_vec_N), "," , int(entry.earth_mag_vec_Z) 
    f_csv.close()
    return
       

 
########## User Interface Routines, functions and classes ##########


class flan_options :
    """a simple storage object for the user's selected options"""
    def __init__(self) :
        self.telemetry_filename = "None"
        self.waypoint_filename = "None"
        self.GE_filename = "None"
        self.CSV_filename = "None"
        self.telemetry_selector = int(1)
        self.waypoint_selector = int(0)
        self.GE_selector = int(1)
        self.CSV_selector = int(0)
        self.loglevel = 0
        self.gps_delay_correction = 0
        pass

def saveObject(filename, object_h) :
    """Save an object along with it's state permanently to a file"""
    file_h = open(filename, 'w')
    pickle.dump(object_h,file_h)
    file_h.close()
    return

def loadObject(filename) :
    """load an object along with it's state from a file"""
    file = open(filename, 'r')
    object = pickle.load(file)
    file.close()
    return object

def process_telemetry():
    """ Called when start button is pressed. 
    Setup a scrollable text window to report activities, and then call the main
    KML / KMZ conversion routines using the options that the user has chosen"""
    myframe.start_button.configure(state = "disabled")
    if (( os.path.exists(myframe.GE_filename)) and (myframe.GE_var.get() ==1) ):
         message = 'The following file already exists.\n'+ myframe.GE_filename + \
                  '\n Do you want to overwrite it ?'
         if askyesno(title = 'Confirm File Overwrite', message = message) :
             pass
         else :
            myframe.start_button.configure(state = "active")
            return
    if (( os.path.exists(myframe.CSV_filename)) and (myframe.CSV_var.get() == 1)) :
         message = 'The following file already exists.\n'+ myframe.CSV_filename + \
                  '\n Do you want to overwrite it ?'
         if askyesno(title = 'Confirm File Overwrite', message = message) :
             pass
         else :
            myframe.start_button.configure(state = "active")
            return
    w = flan_text_frame()
    w.grid(row = 1, column = 0)
    sys.stdout = w # We re-direct all standard out to the new scrollable window
    sys.stderr = w
    print "The following text is a log of the conversion process:\n"
    
    options.telemetry_selector = myframe.tel_var.get()   
    options.telemetry_filename = myframe.telemetry_filename 
    options.waypoint_selector = myframe.way_var.get()
    options.waypoint_filename = myframe.waypoint_filename
    options.GE_filename = myframe.GE_filename 
    options.GE_filename_kml = re.sub("\.kmz",".kml",options.GE_filename)
    options.CSV_selector = myframe.CSV_var.get()
    options.CSV_filename = myframe.CSV_filename 
    options.altitude_correction = myframe.scl.get()
    options.gps_delay_correction = myframe.gps_scl.get()
    
    if (options.waypoint_selector == 1 and options.telemetry_selector == 0):
        if (not waypoints_do_not_need_telemetry(options.waypoint_filename)): # movable origin
               showinfo(title ="Movable Origin; Select Telemetry file\n" ,      
                       message = "It appears that the waypoint file has a movable \n" +
                        "origin (the boot up location of the plane) and so\n"      +
                        "to process this waypoint file, the software needs you\n"  +
                        "to select a telemetry file. Please choose and select\n"   +
                        "a telemetry file for this waypoints.h file\n"             +
                        "\n"                                                       +
                        "If you want to see your relative waypoints in\n"          +
                        "Google Earth without using telemetry, then you can\n"  +    
                        "alter the definition of the origin in waypoints.h to\n"   +
                        "be Fixed a origin." )
               print "Waypoints.h file has a movable origin. Telemetry file required;"
               print "Or change waypoint origin from movable to Fixed."
               myframe.start_button.configure(state = 'active')
               return
            
    print "Processing files, log level",options.loglevel,"..."
    if options.loglevel > 1 :
       print "Telemetry Selector", options.telemetry_selector
       print "Telemetry File" , options.telemetry_filename
       print "Waypoint Selector", options.waypoint_selector
       print "Waypoint Filename", options.waypoint_filename
       print "GE KMZ Filename", options.GE_filename
       print "Name used for temporary kml file is ", options.GE_filename_kml
       print "CSV Selector", options.CSV_selector
       print "CSV Filename" , options.CSV_filename
       print "Altitude Correction" , options.altitude_correction
       print "GPS Delay Correction", options.gps_delay_correction
 
    saveObject( "flan_config",options) # save user selected options to a file
    if (options.telemetry_selector == 1):
        print "Analyzing telemetry and creating flight log book"
        log_book = create_log_book(options)
        print "Writing to temporary telemetry kml file"
        create_telemetry_kmz(options, log_book) 
    elif ((options.waypoint_selector ==1 ) and (options.telemetry_selector == 0)):
        print "Writing waypoint KML file"
        create_waypoint_kmz(options)
    else :
        print showerror(title="Processing Error",
                        message = "Processing started without an input file being selected")
        return
    print "Zipping up KML into a KMZ File"
    wrap_kml_into_kmz(options)
    if (options.CSV_selector == 1):
        print "Writing CSV file"
        write_csv(options,log_book)
    message_text = "Flight Analyzer Processing Completed"
    showinfo(title  = "Processing Completed", message = message_text)
    print message_text
    myframe.start_button.configure(state = "active")
    return  
    
class  flan_frame(Frame) : # A window frame for the Flight Analyzer
    """ Create window frame for the user to select options for the Flight Analyzer"""
    def __init__(self, parent = None):
        """Initialise the main window of flan.py"""
        Frame.__init__(self, parent)
        self.grid(row = 0, column = 0, sticky = NSEW)

        self.telemetry_filename = options.telemetry_filename
        self.waypoint_filename = options.waypoint_filename
        self.GE_filename = options.GE_filename
        self.CSV_filename = options.CSV_filename
        
        
        Label(self, text = "Inputs:-", anchor=W).grid(row = 1, column = 1, sticky=W) 
        self.none = "None" 
        self.tel_var = IntVar()
        self.TelemetryCheck = Checkbutton(self, text = "Telemetry.txt",
                    variable = self.tel_var, command = self.telemetry_selected, anchor=W)
        if (options.telemetry_selector == 1) : self.TelemetryCheck.select()
        else: self.TelemetryCheck.deselect()
        self.TelemetryCheck.grid(row = 2, column = 1, sticky = W)
        Label(self, text = "File:").grid(row = 2, column = 2, sticky = W)
        cropped = self.crop_filename(self.telemetry_filename)
        self.TelFileShown = Label(self, text = cropped)
        self.TelFileShown.grid(row = 2, column = 3, sticky = W)
        Button(self, text = "Choose", command = self.choose_file_telemetry).grid(row =2, column=4)

        self.way_var = IntVar()
        self.WaypointsW = Checkbutton(self, text = "Waypoints.h",
                    variable = self.way_var, command = self.waypoint_selected,anchor=W)
        if (options.waypoint_selector == 1) : self.WaypointsW.select()
        else: self.WaypointsW.deselect()
        self.WaypointsW.grid(row = 3, column = 1, sticky=W)
        Label(self, text = "File:", anchor=W).grid(row = 3, column = 2, sticky=W)
        cropped = self.crop_filename(self.waypoint_filename)
        self.WaypointsFileShown = Label(self, text = cropped, anchor=W)
        self.WaypointsFileShown.grid(row = 3, column = 3, sticky=W)
        Button(self, text = "Choose", command = self.choose_file_waypoint).grid(row = 3, column = 4)

        Label(self, text = "   ", anchor=W).grid(row = 4, column = 1, sticky=W)
        Label(self, text = "Outputs:-", anchor=W).grid(row = 5, column = 1, sticky=W)
        
        self.GE_var = IntVar()
        self.GE = Checkbutton(self, text ="Google Earth KMZ",variable = self.GE_var,  \
                              command = self.GE_selected , anchor=W)
        if (options.GE_selector ==1 ) :self.GE.select()
        else : self.GE.deselect()
        self.GE.grid( row = 6 , column = 1, sticky = "W")
        Label(self, text = "File:", anchor=W).grid(row = 6, column = 2, sticky=W)
        cropped = self.crop_filename(self.GE_filename)
        self.GE_FileShown = Label(self,text = cropped, anchor = W)
        self.GE_FileShown.grid(row = 6, column = 3, sticky = W)
        

        self.CSV_var = IntVar()
        self.CSV = Checkbutton(self, text = "Spreadsheet CSV",
                        variable = self.CSV_var, command = self.CSV_selected, anchor=W)
        if (options.CSV_selector ==1 ) :self.CSV.select()
        else : self.CSV.deselect()
        self.CSV.grid( row = 7 , column = 1, sticky=W)
        Label(self, text = "File:", anchor=W).grid(row = 7, column = 2, sticky=W)
        cropped = self.crop_filename(self.CSV_filename)
        self.CSV_FileShown = Label(self,text = cropped, anchor = W)
        self.CSV_FileShown.grid(row = 7, column = 3, sticky = W)
        
        Label(self, text = "    ", anchor=W).grid(row = 8, column = 1, sticky=W)
        
        Label(self, text = "Altitude\nCorrection", anchor=W).grid(row = 9, column = 1, sticky=W)
        self.scl = Scale(self, from_=30, to=-30, tickinterval =20, resolution = 2)
        self.scl.grid(row=10, column = 1, sticky=W)

        Label(self, text = "GPS Delay\nCorrection", anchor=W).grid(row = 9, column = 2, sticky=W)
        self.gps_scl = Scale(self, from_=15, to=0, tickinterval = 5, resolution = 1)
        self.gps_scl.set(options.gps_delay_correction)
        self.gps_scl.grid(row=10, column = 2, sticky=W)


        self.start_button = Button(self, text = 'Start', command = process_telemetry , state = "disabled")
        self.start_button.grid(row = 10,column = 3)
        self.set_start_state()
        Button(self, text = 'Quit', command = root.quit).grid(row = 10,column = 4)
        
        Label(self, text = "   ", anchor=W).grid(row = 10, column = 5, sticky=W) # add space to right
        Label(self, text = "   ", anchor=W).grid(row = 10, column =0, sticky=W)  # add space to left
        return

    def crop_filename(self,filename):
        """Crop a filename for display pourposes"""
        max_length = 72
        newname = filename
        if len(filename) > max_length :
        ##  The following commented code attempted to crop to whole file names
        ##            index = 0
        ##            file_tree = []
        ##            file_parts = os.path.split(filename)
        ##            filename = file_parts[1]
        ##            file_tree.append(filename)
        ##            basename = file_parts[0]
        ##            while ((len(filename) != 0) and (index <= 20)):
        ##                file_parts = os.path.split(basename)
        ##                filename = file_parts[1]
        ##                file_tree.append(file_parts[1])
        ##                basename = file_parts[0]
        ##                index += 1
        ##            remainder = basename
        ##            print "remainder is", basename
        ##            first_time = True
        ##            for a_name in file_tree :
        ##                if (first_time == True) :
        ##                    newname = a_name
        ##                    first_time = False
        ##                else:
        ##                    newname = os.path.join(a_name,newname)
        ##                print "newname is" , newname
        ##                if len(newname) > (max_length - 5):
        ##                    break
        ##            print "cropped filename is ", newname
        ##            print "length of newname is" ,len(newname)
        ##            newname = " ... " + newname
        ##
            newname = filename[(len(filename)- (max_length - 5)):]
            newname = " ... " + newname
            
            return(newname)
        else :
            return(newname)   
            

    def set_output_filenames_telemetry(self):
        """Set the output filenames based on the main input filename
        e.g. telmetry.txt, creates telemetry.kmz and telemety.csv"""
        if self.telemetry_filename == "None" :
            return
        else :
            self.GE_filename = re.sub("\.[tT][xX][tT]",".kmz",self.telemetry_filename)
            self.GE_FileShown.destroy()
            cropped = self.crop_filename(self.GE_filename)
            self.GE_FileShown = Label(self,text = cropped, anchor = W)
            self.GE_FileShown.grid(row = 6, column = 3, sticky = W)
            self.CSV_filename = re.sub("\.[tT][xX][tT]",".csv",self.telemetry_filename)
            self.CSV_FileShown.destroy()
            cropped = self.crop_filename(self.CSV_filename)
            self.CSV_FileShown = Label(self,text = cropped, anchor = W)
            self.CSV_FileShown.grid(row = 7, column = 3, sticky = W)
            return

    def set_output_filenames_waypoint(self):
        """Set the output filenames based on the main input filename"""
        if self.waypoint_filename == "None" :
            return
        else :
            self.GE_filename = re.sub("\.h",".kmz",self.waypoint_filename)
            self.GE_FileShown.destroy()
            cropped = self.crop_filename(self.GE_filename)
            self.GE_FileShown = Label(self,text = cropped, anchor = W)
            self.GE_FileShown.grid(row = 6, column = 3, sticky = W)
            self.CSV_filename = "None"
            self.CSV_FileShown.destroy()
            cropped = self.crop_filename(self.CSV_filename)
            self.CSV_FileShown = Label(self,text = cropped, anchor = W)
            self.CSV_FileShown.grid(row = 7, column = 3, sticky = W)
            return
        
    def choose_file_telemetry(self) :
        """When user chooses telemetry file, update GE and CSV file names using the
        basename of the telemetry file"""
        old_filename = self.telemetry_filename
        if old_filename != "None" :
            file_parts = os.path.split(old_filename) 
            self.telemetry_filename = tkFileDialog.askopenfilename(parent=self,
                title='Choose a telemetry file', initialdir = file_parts[0])
        else: self.telemetry_filename = tkFileDialog.askopenfilename(parent=self,
                    title='Choose a telemetry file')
        if self.telemetry_filename != "":
              match = re.match(".*\.[tT][xX][tT]$",self.telemetry_filename) # match a .txt file
              if match :
                  self.set_output_filenames_telemetry()
              else:
                  showinfo('Telemetry files end in .txt (or .TXT)',  \
                           'Telemetry files must end in .txt (or .TXT)')
                  self.telemetry_filename = old_filename
        else:
            self.telemetry_filename = old_filename
        self.TelFileShown.destroy()
        cropped = self.crop_filename(self.telemetry_filename)
        self.TelFileShown = Label(self, text = cropped, anchor=W)
        self.TelFileShown.grid(row = 2, column = 3, sticky=W)
        self.set_start_state() 
        return       

    def choose_file_waypoint(self) :
        """create a dialogue window for the user to select a waypoint file"""
        old_filename = self.waypoint_filename
        if old_filename != "None" :
            file_parts = os.path.split(old_filename) 
            self.waypoint_filename = tkFileDialog.askopenfilename(parent=self,
                title='Choose a waypoint.h file', initialdir = file_parts[0])
        else: self.waypoint_filename = tkFileDialog.askopenfilename(parent=self,
                    title='Choose a waypoint.h file')
        if (self.waypoint_filename == "") :
            self.waypoint_filename = old_filename
        else :
            match = re.match(".*\.h$",self.waypoint_filename)
            if match :
                self.WaypointsFileShown.destroy()
                cropped = self.crop_filename(self.waypoint_filename)
                self.WaypointsFileShown = Label(self, text = cropped, anchor=W)
                self.WaypointsFileShown.grid(row = 3, column = 3, sticky=W)
                self.set_start_state()
            else :
                showinfo('Waypoint filenames end in .h', 'Waypoint filenames must end in .h')
                self.waypoint_filename = old_filename
        return

    def set_start_state_active(self) :
        """Check that parameters are all correct before finally setting the
        Start button to be active"""
        # There is nothing to check at the moment !
        self.start_button.configure(state = "active") 

    def set_start_state(self):
        """Enable or Disable the start button depending on whether the user
        has provided enough information"""

        ### First, make sure output files are correctly named
        if ((self.tel_var.get() == 1) and (self.way_var.get() == 0)):
            self.set_output_filenames_telemetry()
        elif ((self.tel_var.get() == 1) and (self.way_var.get() == 1)):
            self.set_output_filenames_telemetry()
        elif ((self.tel_var.get() == 0)  and (self.way_var.get() == 1)):
            self.set_output_filenames_waypoint()
        elif ((self.tel_var.get() == 0 )and  (self.way_var.get() == 0)):
              pass # Leave evertyhing alone, nothing selected

        ### Ensure Start Button is put into the correct state
        
        if (((self.telemetry_filename != self.none )
            and (self.tel_var.get() == 1) ) 
            and
           ((self.waypoint_filename != self.none )
            and (self.way_var.get() == 1))):
                self.set_start_state_active()
                
        elif (((self.telemetry_filename != self.none )
            and (self.tel_var.get() == 1)) 
            and
            (self.way_var.get() == 0)):
                 self.set_start_state_active()
                 
        elif (((self.tel_var.get() == 0) ) 
            and  ((self.waypoint_filename != self.none ) and
                  (self.way_var.get() == 1))):
            if (self.CSV_var.get() == 1) :
                showinfo(title = "Turning off CSV File Creation",
                         message = "Turning off Telemetry CSV file selection as only waypoints are selected")
                self.CSV.deselect()
            self.set_start_state_active()
            
        else:
            self.start_button.configure(state = "disabled")
        self.start_button.grid(row = 10, column = 3)
        
        return

    def telemetry_selected(self):
        if (self.tel_var.get() == 1) and (self.telemetry_filename == self.none):
            showinfo('Select File','Please Choose a Telemetry File')
        self.set_start_state()
        return

    def waypoint_selected(self):
        if (self.way_var.get() == 1) and (self.waypoint_filename == self.none):
            showinfo('Select File','Please Choose a Waypoint File')
        if (self.way_var.get() == 1) :
            self.GE.select()
        self.set_start_state()
        return

    def GE_selected(self) :
        showinfo('GE KMZ always selected',
                 """In this version of the software, Goodle Earth KMZ has to be enabled""")
        self.GE.select()
        self.set_start_state()
        return

    def CSV_selected(self) :
        self.set_start_state()
        return

class flan_text_frame(Frame):
    """ Provide a scrollable text window for all logged output from flan.py
    including any errors that are encountered."""
    def __init__(self, parent = None):
        Frame.__init__(self, parent)
        self.grid(row = 0, column = 0, sticky = NSEW)
        self.scrollbar = Scrollbar(self)
        self.scrollbar.grid(row = 1, column = 1, sticky = NS) 
        self.scrollbar2 = Scrollbar(self, orient = HORIZONTAL)
        self.scrollbar2.grid(row =2, column =0, sticky = EW)
        self.text = Text (self, wrap = NONE, yscrollcommand = self.scrollbar.set,
                          xscrollcommand = self.scrollbar2.set,
                          height= 19,relief=SUNKEN)
        self.text.grid(row = 1, column = 0, sticky = NSEW)
        self.scrollbar.config(command=self.text.yview)
        self.scrollbar2.config(command=self.text.xview)
        return
        
    def write(self, string) :
        self.text.insert(END,string)
        self.text.focus()  # Set flashing cursor to denote where next text will appear
        self.text.see(END) # Scroll the text to the end so user sees the latest print statements
        self.text.update()
        return

########## Start of the Main Program ##########

debug = 0 # set this to 1 of you want lot's of debug info to be printed.
GPS = 0
IMU = 1
            
if __name__=="__main__":

    instructions = "flan.py:  Convert a MatrixPilot telemetry and waypoints.h file " + \
               "to Google Earth Placmarks (kmz) File \n "
    
    if len(sys.argv) == 1:
        flight_clock = clock() # flight_clock is object name with global scope
        mycolors = colors()    # mycolors is object name with global scope
        try :
            options = loadObject("flan_config")
            # Allow people that are upgrading their flan
            # to have new options setup for them.
            try:
                options.gps_delay_correction
            except:
                options.gps_delay_correction = 0
        except:
            options = flan_options() # Assume we have not run the program before.
        root = Tk()
        root.title("Flight Analyzer")
        myframe = flan_frame()
        myframe.grid(row = 0,column= 0) 
        w = Canvas(root, width=600, height=300)
        working_dir = os.getcwd()
        image_dir = "images"
        #image_file = "fa_banner_300x300.gif"
        image_file = "fa_logo_master2_600_300.gif"
        image_full_name = os.path.join(image_dir, image_file)
        try:
            imgobj = PhotoImage(file = image_full_name)
            w.imgobj = w.create_image(300,150,image = imgobj)
            
        except:
            pass
        w.grid(row = 1,column= 0, sticky = NSEW) 
        mainloop() # view at process_telemetry() for main telemetry processing
    else:
        print instructions

root.quit() # close the main window
    

    
    
