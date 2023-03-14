/* SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * SWIG script with instructions allowing access to AJA's NTV2 library from
 * python.
 */

%module ajantv2

%{
#define AJALinux 1
#define AJA_LINUX 1
#define AJAExport

#include <ajantv2/includes/ajatypes.h>
#include <ajantv2/includes/ntv2enums.h>
#include <ajantv2/includes/ntv2driverinterface.h>
#include <ajantv2/includes/ntv2linuxdriverinterface.h>
#include <ajantv2/includes/ntv2card.h>
#include <ajantv2/includes/ntv2devicescanner.h>
%}

#define AJALinux 1
#define AJA_LINUX 1
#define AJAExport

%include <std_string.i>
%include <stdint.i>
%include <typemaps.i>

// ntv2utils.h declares this but its not in the library.
%ignore NTV2SmpteLineNumber::operator==;
// other problematic definitions (don't declare global variables in header files)
%ignore gNTV2_DEPRECATE;
%ignore __AJA_trigger_link_error_if_incompatible__;
// ambiguous declaration
%ignore SetAudioOutputMonitorSource;

%apply std::string & OUTPUT { std::string & outSerialNumberString };
%apply ULWord & OUTPUT { ULWord & outPCIDeviceID };
%apply ULWord & OUTPUT { ULWord & outNumBytes };
%apply std::string & OUTPUT { std::string & outDateStr };
%apply std::string & OUTPUT { std::string & outTimeStr };
%apply bool & OUTPUT { bool & outIsFailSafe };

%include <ajantv2/includes/ajatypes.h>
%include <ajantv2/includes/ntv2enums.h>
%include <ajantv2/includes/ntv2driverinterface.h>
%include <ajantv2/includes/ntv2linuxdriverinterface.h>
%include <ajantv2/includes/ntv2card.h>
%include <ajantv2/includes/ntv2devicescanner.h>
