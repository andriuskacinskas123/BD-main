readChannelID = 2089615;

fieldID2 = 2;

% Channel Read API Key
% If your channel is private, then enter the read API
% Key between the '' below:
readAPIKey = 'T0G73G5T98U8G70M';

% Read second data variable
data2 = thingSpeakRead(readChannelID, 'Field', fieldID2, 'NumPoints', 300, 'ReadKey', readAPIKey);

%% Process Data

% Concatenate the two data variables
data = data2;
ylim = [-20,40];

%% Visualize Data

area(data);