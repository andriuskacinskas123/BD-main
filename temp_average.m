% Set up the ThingSpeak channel and API key
channelID = 2089615; % Replace with your channel ID
readAPIKey = 'T0G73G5T98U8G70M'; % Replace with your read API key

% Define time span for the data
startDate = datetime('2023-05-02','Format','yyyy-MM-dd');
endDate = datetime('now','Format','yyyy-MM-dd');

% Read the data from field 2 of your channel
data = thingSpeakRead(channelID, 'Fields', 3, 'ReadKey', readAPIKey, 'DateRange', [startDate, endDate]);

% Calculate the average moisture level and standard deviation
avgMoisture = mean(data);
stdMoisture = std(data);

% Calculate the average loss of moisture over several days
numDays = daysact(startDate, endDate);
avgMoistureLoss = (data(1) - data(end)) / numDays;

% Display the average moisture level, standard deviation, and average loss of moisture over several days
disp(['The average temperature level is ', num2str(avgMoisture), '%.']);
disp(['The standard deviation of temperature is ', num2str(stdMoisture), '%.']);
disp(['The average loss of temperature over ', num2str(numDays), ' days is ', num2str(avgMoistureLoss), '% per day.']);